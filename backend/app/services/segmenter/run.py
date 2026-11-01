"""分段切句：调用模型、按 complete 续跑、把片段偏移平移到全文坐标。

这里没有本地切分，也没有内容比对。
唯一的数值处理是「偏移 + base」与「越界保护」，用于避免死循环。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ...schemas.llm.segment import SegmentParagraph, SegmentResult, SegmentSentence
from ..llm.client import LLMResult
from ..prompt_loader import load_prompt, render

PROMPT_VERSION = "segment_v1"
PROMPT_FILE = "segment_v1.md"


@dataclass
class SegmentOutcome:
    status: str  # segmented | incomplete
    title: str | None
    paragraphs: list[SegmentParagraph]
    stats: dict = field(default_factory=dict)
    attempts: int = 0
    runs: list[LLMResult] = field(default_factory=list)

    @property
    def sentence_count(self) -> int:
        return sum(len(p.sentences) for p in self.paragraphs)


def _shift(paragraphs: list[SegmentParagraph], base: int) -> list[SegmentParagraph]:
    shifted = []
    for para in paragraphs:
        sentences = [
            SegmentSentence(
                index=s.index,
                text=s.text,
                char_start=s.char_start + base,
                char_end=s.char_end + base,
            )
            for s in para.sentences
        ]
        if sentences:
            shifted.append(SegmentParagraph(index=para.index, sentences=sentences))
    return shifted


def _renumber(paragraphs: list[SegmentParagraph]) -> list[SegmentParagraph]:
    out: list[SegmentParagraph] = []
    counter = 0
    for para_index, para in enumerate((p for p in paragraphs if p.sentences), start=1):
        sentences = []
        for sentence in para.sentences:
            counter += 1
            sentences.append(
                SegmentSentence(
                    index=counter,
                    text=sentence.text,
                    char_start=sentence.char_start,
                    char_end=sentence.char_end,
                )
            )
        out.append(SegmentParagraph(index=para_index, sentences=sentences))
    return out


def run(client, raw_text: str, *, model: str, max_continuations: int = 3) -> SegmentOutcome:
    system, user_template = load_prompt(PROMPT_FILE)

    base = 0
    merged: list[SegmentParagraph] = []
    runs: list[LLMResult] = []
    stats: dict = {}
    title: str | None = None
    complete = False
    attempts = 0

    for _ in range(max_continuations + 1):
        excerpt = raw_text[base:]
        if not excerpt.strip():
            break

        attempts += 1
        user = render(user_template, TEXT=excerpt)
        result = client.chat_json(
            kind="segment",
            system=system,
            user=user,
            model=model,
            max_tokens=8192,
            context={"excerpt": excerpt},
        )
        runs.append(result)

        payload = SegmentResult.model_validate(result.data)
        title = title or payload.title
        if payload.stats and not stats:
            stats = payload.stats.model_dump()

        shifted = _shift(payload.paragraphs, base)
        merged.extend(shifted)

        if payload.complete:
            complete = True
            break

        last_end = max((s.char_end for p in shifted for s in p.sentences), default=0)
        if last_end <= base:
            break  # 没有前进，避免死循环
        base = min(last_end, len(raw_text))
        if base >= len(raw_text):
            break

    paragraphs = _renumber(merged)
    status = "segmented" if complete and paragraphs else "incomplete"
    return SegmentOutcome(
        status=status,
        title=title,
        paragraphs=paragraphs,
        stats=stats,
        attempts=attempts,
        runs=runs,
    )
