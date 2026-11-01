from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SegmentSentence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    index: int = Field(ge=1)
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)


class SegmentParagraph(BaseModel):
    model_config = ConfigDict(extra="ignore")

    index: int = Field(ge=1)
    sentences: list[SegmentSentence] = Field(default_factory=list)


class SegmentStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sentence_count: int | None = None
    word_count: int | None = None
    language: str | None = None


class SegmentResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    complete: bool = True
    paragraphs: list[SegmentParagraph] = Field(default_factory=list)
    stats: SegmentStats | None = None

    def sentence_total(self) -> int:
        return sum(len(p.sentences) for p in self.paragraphs)
