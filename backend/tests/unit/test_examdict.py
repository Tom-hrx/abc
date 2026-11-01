from app.extensions import db
from app.models import ExamWord
from app.services.examdict.lookup import build_label, lookup


def test_build_label_without_exam_years():
    assert build_label("zhongkao", "high", [], []) == "中考考纲·高频"


def test_build_label_with_exam_years():
    assert build_label("zhongkao", "high", [2025], ["北京卷"]) == "中考考纲·高频·2025 北京卷"


def test_build_label_unknown_level_returns_none():
    assert build_label(None, "high", [2025], ["北京卷"]) is None


def _seed(lemma="address", pos="v.", level="zhongkao", band="high", years=None, papers=None):
    db.session.add(
        ExamWord(
            lemma=lemma,
            pos=pos,
            level=level,
            band=band,
            years_json=years or [],
            papers_json=papers or [],
            senses_json=[],
            source="test",
        )
    )
    db.session.commit()


def test_lookup_returns_tag_when_row_exists(app):
    _seed()
    tag = lookup("Address", "zhongkao")
    assert tag.level == "zhongkao"
    assert tag.band == "high"
    assert tag.label == "中考考纲·高频"
    assert tag.source == "table"


def test_lookup_returns_empty_when_missing(app):
    tag = lookup("unknownword", "zhongkao")
    assert tag.label is None
    assert tag.source == "table"


def test_lookup_ignores_other_level(app):
    _seed(level="gaokao")
    tag = lookup("address", "zhongkao")
    assert tag.label is None


def test_lookup_off_and_model_modes(app):
    _seed()
    assert lookup("address", "zhongkao", "off").label is None
    tag = lookup("address", "zhongkao", "model")
    assert tag.label is None and tag.source == "model"
