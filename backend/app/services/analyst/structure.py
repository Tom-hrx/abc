"""整体结构分析：只需要段落划分，不依赖逐句结果。"""
from __future__ import annotations

from ...schemas.llm.structure import StructureResult
from ..llm.client import LLMResult
from ..prompt_loader import load_prompt, render

PROMPT_VERSION = "structure_v1"
PROMPT_FILE = "structure_v1.md"

_LEVEL_LABELS = {"zhongkao": "中考", "gaokao": "高考"}


def build_content(paragraph_texts: list[list[str]] | None, raw_text: str) -> str:
    """按句换行展示段落，避免在本地拼接或改动原文。"""
    if paragraph_texts:
        blocks = []
        for index, sentences in enumerate(paragraph_texts, start=1):
            blocks.append(f"[段落 {index}]")
            blocks.extend(f"- {text}" for text in sentences)
        return "\n".join(blocks)
    return "以下为原文（尚未分段），请自行判断段落结构：\n" + raw_text


def run(
    client,
    *,
    raw_text: str,
    paragraph_texts: list[list[str]] | None,
    target_level: str,
    model: str,
) -> tuple[StructureResult, LLMResult]:
    system, user_template = load_prompt(PROMPT_FILE)
    user = render(
        user_template,
        LEVEL=_LEVEL_LABELS.get(target_level, target_level),
        CONTENT=build_content(paragraph_texts, raw_text),
    )
    result = client.chat_json(
        kind="structure",
        system=system,
        user=user,
        model=model,
        max_tokens=2048,
    )
    return StructureResult.model_validate(result.data), result
