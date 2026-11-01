"""模型调用层：OpenAI 兼容协议 + 指数退避重试 + JSON 解析。

这里唯一允许的“文本处理”是解析响应信封（去掉可能的 ```json 围栏），
绝不触碰文章正文。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from ...errors import AppError, ErrorCode
from .cost import estimate_cost_usd
from .fake import FakeProvider

_RETRYABLE: tuple[type[BaseException], ...] = ()


def _retryable_types() -> tuple[type[BaseException], ...]:
    global _RETRYABLE
    if _RETRYABLE:
        return _RETRYABLE
    import openai

    types = [openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError]
    _RETRYABLE = tuple(types)
    return _RETRYABLE


@dataclass
class LLMResult:
    data: dict
    raw: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


def parse_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AppError(ErrorCode.LLM_BAD_OUTPUT, f"模型返回的不是合法 JSON：{exc.msg}", 502, raw_head=text[:300]) from exc
    if not isinstance(parsed, dict):
        raise AppError(ErrorCode.LLM_BAD_OUTPUT, "模型返回的 JSON 顶层不是对象", 502)
    return parsed


class LLMClient:
    def __init__(self, config) -> None:
        self.config = config
        self.mode = self._resolve_mode(config)
        self._client = None
        self._fake = FakeProvider() if self.mode == "fake" else None

    @staticmethod
    def _resolve_mode(config) -> str:
        mode = (config.LLM_MODE or "auto").lower()
        if mode == "auto":
            return "openai" if config.LLM_API_KEY else "fake"
        if mode not in ("openai", "fake"):
            raise ValueError(f"未知的 LLM_MODE: {mode}")
        return mode

    def chat_json(
        self,
        *,
        kind: str,
        system: str,
        user: str,
        model: str,
        max_tokens: int = 4096,
        context: dict | None = None,
        images: list[str] | None = None,
    ) -> LLMResult:
        if self.mode == "fake":
            return LLMResult(**self._fake.chat_json(
                kind=kind,
                system=system,
                user=user,
                model=model,
                max_tokens=max_tokens,
                context=context,
                images=images,
            ))

        started = time.perf_counter()
        response = self._with_retry(
            lambda: self._openai_call(system=system, user=user, model=model, max_tokens=max_tokens, images=images)
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

        return LLMResult(
            data=parse_json_object(content),
            raw=content,
            model=getattr(response, "model", model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost_usd(input_tokens, output_tokens, self.config),
            latency_ms=latency_ms,
        )

    def _openai_call(self, *, system: str, user: str, model: str, max_tokens: int, images: list[str] | None = None):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.config.LLM_API_KEY,
                base_url=self.config.LLM_BASE_URL,
                timeout=self.config.LLM_TIMEOUT,
            )

        if images:
            user_content: object = [{"type": "text", "text": user}]
            for url in images:
                user_content.append({"type": "image_url", "image_url": {"url": url}})
        else:
            user_content = user

        return self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            temperature=self.config.LLM_TEMPERATURE,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            extra_body={"enable_thinking": False},
        )

    def _with_retry(self, call):
        from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

        retryer = Retrying(
            stop=stop_after_attempt(max(1, self.config.LLM_MAX_RETRIES)),
            wait=wait_exponential_jitter(initial=1, max=8),
            retry=retry_if_exception_type(_retryable_types()),
            reraise=True,
        )
        try:
            return retryer(call)
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 - 统一转成对外错误码
            raise AppError(ErrorCode.LLM_UNAVAILABLE, f"模型调用失败：{exc}", 502) from exc
