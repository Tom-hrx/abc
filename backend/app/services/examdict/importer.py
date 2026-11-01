"""词表导入：CSV → exam_words。

列：lemma,pos,level,band,years,papers,senses
- years 用分号分隔，如 `2024;2025`
- papers 用分号分隔，如 `全国乙卷;新课标I卷`
- senses 用分号分隔，如 `处理;演讲`
- 同一 (lemma, pos, level) 重复导入时覆盖更新（幂等）。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ...extensions import db
from ...models import ExamWord


def _split(value: str | None, cast=str) -> list:
    if not value:
        return []
    return [cast(item.strip()) for item in value.split(";") if item.strip()]


def import_csv(path: str | Path, source: str | None = None) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    created = updated = skipped = 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            lemma = (row.get("lemma") or "").strip().lower()
            level = (row.get("level") or "").strip().lower()
            if not lemma or level not in ("zhongkao", "gaokao"):
                skipped += 1
                continue

            pos = (row.get("pos") or "").strip()
            band = (row.get("band") or "mid").strip().lower()
            years = _split(row.get("years"), int)
            papers = _split(row.get("papers"))
            senses = _split(row.get("senses"))
            row_source = (row.get("source") or source or path.name).strip()

            existing = ExamWord.query.filter_by(lemma=lemma, pos=pos, level=level).first()
            if existing is None:
                db.session.add(
                    ExamWord(
                        lemma=lemma,
                        pos=pos,
                        level=level,
                        band=band,
                        years_json=years,
                        papers_json=papers,
                        senses_json=senses,
                        source=row_source,
                    )
                )
                created += 1
            else:
                existing.band = band
                existing.years_json = years
                existing.papers_json = papers
                existing.senses_json = senses
                existing.source = row_source
                updated += 1

    db.session.commit()
    total = ExamWord.query.count()
    return {
        "file": str(path),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total_rows": total,
    }


def dump_rows(limit: int = 20) -> list[dict]:
    rows = ExamWord.query.order_by(ExamWord.lemma).limit(limit).all()
    return [
        {
            "lemma": r.lemma,
            "pos": r.pos,
            "level": r.level,
            "band": r.band,
            "years": r.years_json,
            "papers": r.papers_json,
            "senses": r.senses_json,
        }
        for r in rows
    ]
