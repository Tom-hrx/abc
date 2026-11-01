"""考点词表查询：模型给出 lemma，这里查表回填标签。

边界说明：
- 查表不产生、不修改任何文本，只读数据库；
- 查不到就返回空标签（宁缺勿假），不猜测年份或卷别。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func

from ...extensions import db
from ...models import ExamWord

LEVEL_NAMES = {"zhongkao": "中考", "gaokao": "高考"}
BAND_NAMES = {"high": "高频", "mid": "中频", "low": "低频"}
_BAND_RANK = {"high": 0, "mid": 1, "low": 2}


@dataclass
class ExamTag:
    label: str | None = None
    level: str | None = None
    band: str | None = None
    years: list[int] = field(default_factory=list)
    papers: list[str] = field(default_factory=list)
    source: str = "table"

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "level": self.level,
            "band": self.band,
            "years": self.years,
            "papers": self.papers,
            "source": self.source,
        }


def build_label(level: str | None, band: str | None, years: list[int], papers: list[str]) -> str | None:
    if not level:
        return None
    parts = [f"{LEVEL_NAMES.get(level, level)}考纲"]
    if band:
        parts.append(BAND_NAMES.get(band, band))
    if years:
        year = years[0]
        parts.append(f"{year} {papers[0]}" if papers else str(year))
    return "·".join(parts)


def lookup(lemma: str | None, target_level: str, source_mode: str = "table") -> ExamTag:
    if source_mode == "off":
        return ExamTag(source="off")
    if source_mode == "model":
        # 完全信任模型自报时，服务端不提供任何出处信息
        return ExamTag(source="model")
    if not lemma:
        return ExamTag(source="table")

    key = lemma.strip().lower()
    if not key:
        return ExamTag(source="table")

    rows = (
        db.session.query(ExamWord)
        .filter(func.lower(ExamWord.lemma) == key, ExamWord.level == target_level)
        .all()
    )
    if not rows:
        return ExamTag(source="table")

    rows.sort(key=lambda w: (_BAND_RANK.get(w.band or "mid", 9), w.pos or ""))
    best = rows[0]
    years = list(best.years_json or [])
    papers = list(best.papers_json or [])
    return ExamTag(
        label=build_label(best.level, best.band, years, papers),
        level=best.level,
        band=best.band,
        years=years,
        papers=papers,
        source="table",
    )
