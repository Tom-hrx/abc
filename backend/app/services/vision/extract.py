"""图片识别：把图片交给视觉模型转写成文本。

仍然遵守「本地不做文本处理」：这里只做 base64 编码（传输格式，不是文本处理）、
调用模型、按顺序拼接各页结果。
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field

from ...errors import AppError, ErrorCode
from ...schemas.llm.vision import VisionResult
from ..llm.client import LLMResult
from ..prompt_loader import load_prompt

PROMPT_VERSION = "vision_v1"
PROMPT_FILE = "vision_v1.md"


@dataclass
class VisionPage:
    index: int
    text: str
    complete: bool
    notes: str | None


@dataclass
class VisionOutcome:
    text: str
    title: str | None
    pages: list[VisionPage] = field(default_factory=list)
    runs: list[LLMResult] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return bool(self.pages) and all(page.complete for page in self.pages)

    @property
    def notes(self) -> list[str]:
        return [f"第 {p.index} 张：{p.notes}" for p in self.pages if p.notes]


def to_data_url(data: bytes, mime: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def extract(
    client,
    *,
    images: list[bytes],
    mimes: list[str],
    model: str,
) -> VisionOutcome:
    system, user_prompt = load_prompt(PROMPT_FILE)

    pages: list[VisionPage] = []
    runs: list[LLMResult] = []
    title: str | None = None

    for index, (data, mime) in enumerate(zip(images, mimes), start=1):
        result = client.chat_json(
            kind="vision",
            system=system,
            user=user_prompt,
            model=model,
            max_tokens=8192,
            images=[to_data_url(data, mime)],
            context={"index": index},
        )
        runs.append(result)

        payload = VisionResult.model_validate(result.data)
        pages.append(
            VisionPage(
                index=index,
                text=payload.text.strip(),
                complete=payload.complete,
                notes=payload.notes,
            )
        )
        title = title or payload.title

    text = "\n\n".join(page.text for page in pages if page.text)
    if not text:
        raise AppError(
            ErrorCode.LLM_BAD_OUTPUT,
            "没能从图片里识别出英文正文。换个角度重拍或提高清晰度再试。",
            422,
            notes=" / ".join(f"第 {p.index} 张：{p.notes}" for p in pages if p.notes) or None,
        )

    return VisionOutcome(text=text, title=title, pages=pages, runs=runs)
