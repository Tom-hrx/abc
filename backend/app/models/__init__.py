"""数据模型（M1 范围）。

约定：
- ``raw_text`` 是唯一真相，只存不改。
- ``sentences.text`` 是渲染依据；``char_start/char_end`` 仅用于定位，不做校验。
- 所有偏移来自模型，服务端只做数值平移与越界保护（不涉及文本处理）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300))
    raw_text = db.Column(db.Text, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    source = db.Column(db.String(32), nullable=False, default="paste")
    target_level = db.Column(db.String(16), nullable=False, default="zhongkao")

    char_count = db.Column(db.Integer, nullable=False, default=0)
    word_count = db.Column(db.Integer)
    sentence_count = db.Column(db.Integer)

    # pending | segmented | unsegmented
    segment_status = db.Column(db.String(16), nullable=False, default="pending")
    segment_model = db.Column(db.String(64))
    segment_prompt_version = db.Column(db.String(32))
    segment_attempts = db.Column(db.Integer, default=0)

    # 图片来源信息：页数、识别模型、每页字数、识别备注（text 来源时为空）
    source_meta_json = db.Column(db.JSON)
    extraction_model = db.Column(db.String(64))
    extraction_prompt_version = db.Column(db.String(32))

    structure_json = db.Column(db.JSON)
    structure_model = db.Column(db.String(64))
    structure_prompt_version = db.Column(db.String(32))

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    sentences = db.relationship(
        "Sentence",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Sentence.idx",
        lazy="selectin",
    )

    def to_meta(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "raw_text": self.raw_text,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "source": self.source,
            "source_meta": self.source_meta_json,
            "target_level": self.target_level,
            "segment_status": self.segment_status,
            "segment_model": self.segment_model,
            "segment_prompt_version": self.segment_prompt_version,
            "structure": self.structure_json,
            "can_analyze_structure": True,
            "can_analyze_sentences": self.segment_status == "segmented",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Sentence(db.Model):
    __tablename__ = "sentences"
    __table_args__ = (db.UniqueConstraint("document_id", "idx", name="uq_sentence_doc_idx"),)

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    idx = db.Column(db.Integer, nullable=False)
    para_idx = db.Column(db.Integer, nullable=False)

    text = db.Column(db.Text, nullable=False)
    char_start = db.Column(db.Integer, nullable=False)
    char_end = db.Column(db.Integer, nullable=False)

    translation = db.Column(db.Text)
    difficulty = db.Column(db.Integer)
    structure_hint = db.Column(db.String(200))
    note = db.Column(db.Text)
    analyzed = db.Column(db.Boolean, nullable=False, default=False)

    document = db.relationship("Document", back_populates="sentences")
    grammar = db.relationship(
        "SentenceGrammar", back_populates="sentence", cascade="all, delete-orphan", lazy="selectin"
    )
    vocab = db.relationship(
        "SentenceVocab", back_populates="sentence", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "idx": self.idx,
            "para_idx": self.para_idx,
            "text": self.text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "translation": self.translation,
            "difficulty": self.difficulty,
            "structure_hint": self.structure_hint,
            "note": self.note,
            "analyzed": self.analyzed,
            "grammar": [
                {
                    "label": g.label,
                    "span": g.span,
                    "span_start": g.span_start,
                    "span_end": g.span_end,
                    "explain_cn": g.explain_cn,
                    "exam_tip": g.exam_tip,
                }
                for g in self.grammar
            ],
            "vocab": [
                {
                    "surface": v.surface,
                    "span_start": v.span_start,
                    "span_end": v.span_end,
                    "lemma": v.lemma,
                    "pos": v.pos,
                    "sense_cn": v.sense_cn,
                    "collocations": v.collocations_json or [],
                    "pitfall_cn": v.pitfall_cn,
                    "exam_hint": v.exam_hint,
                    "exam_label": v.exam_label,
                    "exam_level": v.exam_level,
                    "exam_band": v.exam_band,
                    "exam_source": v.exam_source,
                }
                for v in self.vocab
            ],
        }


class SentenceGrammar(db.Model):
    __tablename__ = "sentence_grammar"

    id = db.Column(db.Integer, primary_key=True)
    sentence_id = db.Column(db.Integer, db.ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False, index=True)
    label = db.Column(db.String(32), nullable=False)
    span = db.Column(db.String(200))
    span_start = db.Column(db.Integer)
    span_end = db.Column(db.Integer)
    explain_cn = db.Column(db.Text, nullable=False)
    exam_tip = db.Column(db.Text)

    sentence = db.relationship("Sentence", back_populates="grammar")


class SentenceVocab(db.Model):
    __tablename__ = "sentence_vocab"

    id = db.Column(db.Integer, primary_key=True)
    sentence_id = db.Column(db.Integer, db.ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False, index=True)
    surface = db.Column(db.String(120), nullable=False)
    span_start = db.Column(db.Integer)
    span_end = db.Column(db.Integer)
    lemma = db.Column(db.String(120), index=True)
    pos = db.Column(db.String(16))
    sense_cn = db.Column(db.Text)
    collocations_json = db.Column(db.JSON)
    pitfall_cn = db.Column(db.Text)
    exam_hint = db.Column(db.Text)

    # 由 examdict 查表回填；查不到则为 None（宁缺勿假）
    exam_label = db.Column(db.String(120))
    exam_level = db.Column(db.String(16))
    exam_band = db.Column(db.String(16))
    exam_source = db.Column(db.String(16))

    sentence = db.relationship("Sentence", back_populates="vocab")


class AnalysisRun(db.Model):
    """每次模型调用的账本：成本、耗时、成败。M2 的任务化会复用它。"""

    __tablename__ = "analysis_runs"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = db.Column(db.String(32), nullable=False)
    model = db.Column(db.String(64))
    prompt_version = db.Column(db.String(32))
    ok = db.Column(db.Boolean, nullable=False, default=True)
    error_code = db.Column(db.String(32))
    error_message = db.Column(db.Text)
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    cost_usd = db.Column(db.Float, default=0.0)
    latency_ms = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class ExamWord(db.Model):
    """考点词表。全局共享，不随用户变化；只存词与出处，不存真题原文。"""

    __tablename__ = "exam_words"
    __table_args__ = (db.UniqueConstraint("lemma", "pos", "level", name="uq_exam_word"),)

    id = db.Column(db.Integer, primary_key=True)
    lemma = db.Column(db.String(120), nullable=False, index=True)  # 入库统一小写
    pos = db.Column(db.String(16), nullable=False, default="")
    level = db.Column(db.String(16), nullable=False)  # zhongkao | gaokao
    band = db.Column(db.String(16), nullable=False, default="mid")  # high | mid | low
    years_json = db.Column(db.JSON)
    papers_json = db.Column(db.JSON)
    senses_json = db.Column(db.JSON)
    source = db.Column(db.String(64))
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
