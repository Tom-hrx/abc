from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Difficulty(BaseModel):
    model_config = ConfigDict(extra="ignore")

    level: str | None = None      # A2 / B1 / B2 ...
    exam: str | None = None       # 中考 / 高考
    reason: str | None = None


class Section(BaseModel):
    model_config = ConfigDict(extra="ignore")

    paragraphs: list[int] = Field(default_factory=list)
    role: str
    summary_cn: str


class StructureResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    genre: str
    topic: str
    difficulty: Difficulty = Field(default_factory=Difficulty)
    thesis: str = ""
    sections: list[Section] = Field(default_factory=list)
    logic_flow: list[str] = Field(default_factory=list)
    reading_tips: list[str] = Field(default_factory=list)
