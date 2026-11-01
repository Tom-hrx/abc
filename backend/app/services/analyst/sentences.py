"""逐句精讲：分批调用，按 id 回填。"""
from __future__ import annotations

import json
from typing import Iterable

from ...schemas.llm.sentence import SentenceBatchResult, SentenceItem
from ..llm.client import LLMResult
from ..prompt_loader import load_prompt, render

PROMPT_VERSION = "sentences_v1"
PROMPT_FILE = "sentences_v1.md"

_LEVEL_LABELS = {"zhongkao": "中考", "gaokao": "高考"}


def batched(items: list, size: int) -> Iterable[list]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def analyze_batch(
    client,
    *,
    sentences: list[dict],
    target_level: str,
    model: str,
) -> tuple[list[SentenceItem], LLMResult]:
    system, user_template = load_prompt(PROMPT_FILE)
    user = render(
        user_template,
        LEVEL=_LEVEL_LABELS.get(target_level, target_level),
        SENTENCES=json.dumps(sentences, ensure_ascii=False, indent=1),
    )
    result = client.chat_json(
        kind="sentences",
        system=system,
        user=user,
        model=model,
        max_tokens=4096,
    )
    batch = SentenceBatchResult.model_validate(result.data)
    wanted = {item["id"] for item in sentences}
    return [item for item in batch.sentences if item.id in wanted], result
