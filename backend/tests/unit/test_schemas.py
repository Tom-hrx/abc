import pytest
from pydantic import ValidationError

from app.schemas.llm.segment import SegmentResult
from app.schemas.llm.sentence import SentenceBatchResult


def test_segment_result_parses_minimal_payload():
    payload = {
        "title": "T",
        "complete": False,
        "paragraphs": [
            {"index": 1, "sentences": [{"index": 1, "text": "Hi.", "char_start": 0, "char_end": 3}]}
        ],
    }
    result = SegmentResult.model_validate(payload)
    assert result.complete is False
    assert result.sentence_total() == 1


def test_segment_result_rejects_empty_text():
    with pytest.raises(ValidationError):
        SegmentResult.model_validate(
            {"paragraphs": [{"index": 1, "sentences": [{"index": 1, "text": "", "char_start": 0, "char_end": 0}]}]}
        )


def test_sentence_schema_rejects_unknown_label():
    payload = {
        "sentences": [
            {
                "id": 1,
                "translation": "…",
                "grammar": [{"label": "自创标签", "explain_cn": "…"}],
            }
        ]
    }
    with pytest.raises(ValidationError):
        SentenceBatchResult.model_validate(payload)


def test_sentence_schema_ignores_extra_fields():
    payload = {
        "sentences": [
            {"id": 3, "text": "ignored", "translation": "…", "key_vocab": [], "grammar": []}
        ]
    }
    parsed = SentenceBatchResult.model_validate(payload)
    assert parsed.sentences[0].id == 3
