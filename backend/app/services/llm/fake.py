"""测试替身：用录制好的 JSON 夹具冒充模型。

只有在 LLM_MODE=fake 且没有可用 API Key 时才会用到。
夹具里的偏移可以由 surface 反查得到 —— 这段“查找”只存在于替身内部，
生产路径永远不做任何文本比对或定位。
"""
from __future__ import annotations

import json
from pathlib import Path

from ...errors import AppError, ErrorCode
from .cost import estimate_cost_usd


class FakeProvider:
    def __init__(self, fixture_dir: Path | None = None) -> None:
        self.fixture_dir = fixture_dir or (Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "llm")

    def chat_json(
        self,
        *,
        kind: str,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        context: dict | None = None,
        images: list[str] | None = None,
    ):
        payload = self._load(kind)

        if kind == "vision":
            payload = self._build_vision(payload, context)
        elif kind == "segment":
            payload = self._build_segment(payload, (context or {}).get("excerpt", ""))
        elif kind == "sentences":
            payload = self._fill_spans(payload)

        input_tokens = max(1, len(user) // 4) + max(1, len(system) // 4)
        if images:
            input_tokens += 800 * len(images)  # 粗略折算图片 token
        output_tokens = max(1, len(json.dumps(payload, ensure_ascii=False)) // 4)
        return {
            "data": payload,
            "raw": json.dumps(payload, ensure_ascii=False),
            "model": f"fake:{model}",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": estimate_cost_usd(input_tokens, output_tokens, _FakeCostConfig()),
            "latency_ms": 1,
        }

    def _load(self, kind: str) -> dict:
        path = self.fixture_dir / f"fake_{kind}.json"
        if not path.exists():
            raise AppError(ErrorCode.LLM_UNAVAILABLE, f"缺少夹具文件：{path.name}", 503)
        return json.loads(path.read_text(encoding="utf-8"))

    def _build_vision(self, payload: dict, context: dict | None) -> dict:
        """夹具模式不读图片：只为第 1 张返回示例文本，避免多图时正文重复。"""
        index = int((context or {}).get("index", 1))
        if index == 1:
            return {
                "title": payload.get("title"),
                "text": payload.get("text", ""),
                "complete": payload.get("complete", True),
                "notes": payload.get("notes"),
            }
        return {
            "title": None,
            "text": "",
            "complete": True,
            "notes": "夹具模式：仅第一张图片返回示例文本",
        }

    def _build_segment(self, payload: dict, excerpt: str) -> dict:
        """把夹具里的句子文本定位到本次输入片段上，补出 char_start/char_end。"""
        paragraphs = []
        cursor = 0
        for p_index, para in enumerate(payload.get("paragraphs", []), start=1):
            sentences = []
            for s_index, text in enumerate(para.get("sentences", []), start=1):
                start = excerpt.find(text, cursor)
                if start < 0:
                    start = excerpt.find(text)
                if start < 0:
                    continue  # 夹具与输入不匹配时跳过，避免产生假偏移
                end = start + len(text)
                cursor = end
                sentences.append({"index": s_index, "text": text, "char_start": start, "char_end": end})
            if sentences:
                paragraphs.append({"index": p_index, "sentences": sentences})
        return {
            "title": payload.get("title"),
            "complete": payload.get("complete", True),
            "paragraphs": paragraphs,
            "stats": payload.get("stats"),
        }

    def _fill_spans(self, payload: dict) -> dict:
        """夹具只写 surface，偏移由替身补，便于手写夹具。"""
        for item in payload.get("sentences", []):
            text = item.get("text", "")
            for vocab in item.get("key_vocab", []):
                surface = vocab.get("surface", "")
                start = text.find(surface)
                if start < 0:
                    vocab["span_start"], vocab["span_end"] = 0, 0
                else:
                    vocab["span_start"], vocab["span_end"] = start, start + len(surface)
            for grammar in item.get("grammar", []):
                span = grammar.get("span")
                if span:
                    start = text.find(span)
                    grammar["span_start"], grammar["span_end"] = (start, start + len(span)) if start >= 0 else (0, 0)
        return payload


class _FakeCostConfig:
    LLM_PRICE_IN_PER_1M = 0.15
    LLM_PRICE_OUT_PER_1M = 0.60
