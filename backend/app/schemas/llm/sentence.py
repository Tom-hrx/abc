from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 固定标签表：避免同一语法现象出现五种叫法。改动需同步 prompts/sentences_*.md
GRAMMAR_LABELS = (
    "时态",
    "被动语态",
    "情态动词",
    "虚拟语气",
    "定语从句",
    "状语从句",
    "名词性从句",
    "非谓语-不定式",
    "非谓语-分词",
    "非谓语-动名词",
    "倒装",
    "强调句",
    "比较结构",
    "平行结构",
    "插入语",
    "省略",
    "词类活用",
)

GrammarLabel = Literal[
    "时态",
    "被动语态",
    "情态动词",
    "虚拟语气",
    "定语从句",
    "状语从句",
    "名词性从句",
    "非谓语-不定式",
    "非谓语-分词",
    "非谓语-动名词",
    "倒装",
    "强调句",
    "比较结构",
    "平行结构",
    "插入语",
    "省略",
    "词类活用",
]


class VocabItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    surface: str = Field(min_length=1)
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    lemma: str | None = None
    pos: str | None = None
    sense_cn: str = ""
    collocations: list[str] = Field(default_factory=list)
    pitfall_cn: str | None = None
    exam_hint: str | None = None
    # 模型自评：zhongkao | gaokao | beyond | none。仅作参考，默认以查表为准。
    syllabus_guess: str | None = None


class GrammarItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: GrammarLabel
    span_start: int | None = None
    span_end: int | None = None
    span: str | None = None
    explain_cn: str
    exam_tip: str | None = None


class SentenceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    translation: str = ""
    structure_hint: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    key_vocab: list[VocabItem] = Field(default_factory=list)
    grammar: list[GrammarItem] = Field(default_factory=list)
    note: str | None = None


class SentenceBatchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sentences: list[SentenceItem] = Field(default_factory=list)
