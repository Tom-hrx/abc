"""M1 流水线编排 + 落库。

阶段顺序：segment → structure / sentences。
没有任务队列（M2 才引入），所以这里是同步执行，便于 curl 验证。
"""
from __future__ import annotations

from typing import Any

from ..errors import AppError, ErrorCode
from ..extensions import db
from ..models import AnalysisRun, Document, Sentence, SentenceGrammar, SentenceVocab
from .analyst import sentences as sentence_service
from .analyst import structure as structure_service
from .examdict.lookup import LEVEL_NAMES, lookup
from .llm.client import LLMClient, LLMResult
from .segmenter import run as segmenter


def _record_run(document_id: int, stage: str, result: LLMResult, model: str, prompt_version: str) -> None:
    db.session.add(
        AnalysisRun(
            document_id=document_id,
            stage=stage,
            model=result.model,
            prompt_version=prompt_version,
            ok=True,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
        )
    )


def _record_error(document_id: int, stage: str, model: str, prompt_version: str, exc: AppError) -> None:
    db.session.add(
        AnalysisRun(
            document_id=document_id,
            stage=stage,
            model=model,
            prompt_version=prompt_version,
            ok=False,
            error_code=exc.code,
            error_message=exc.message,
        )
    )
    db.session.commit()


def segment_document(doc: Document, client: LLMClient, config) -> dict[str, Any]:
    model = config.LLM_MODEL_SEGMENT
    try:
        outcome = segmenter.run(
            client,
            doc.raw_text,
            model=model,
            max_continuations=config.LLM_MAX_CONTINUATIONS,
        )
    except AppError as exc:
        _record_error(doc.id, "segment", model, segmenter.PROMPT_VERSION, exc)
        doc.segment_status = "unsegmented"
        db.session.commit()
        raise

    for existing in list(doc.sentences):
        db.session.delete(existing)
    db.session.flush()

    for para in outcome.paragraphs:
        for sentence in para.sentences:
            db.session.add(
                Sentence(
                    document_id=doc.id,
                    idx=sentence.index,
                    para_idx=para.index,
                    text=sentence.text,
                    char_start=sentence.char_start,
                    char_end=sentence.char_end,
                )
            )

    if outcome.title:
        doc.title = outcome.title
    doc.segment_status = "segmented" if outcome.status == "segmented" else "unsegmented"
    doc.segment_model = model
    doc.segment_prompt_version = segmenter.PROMPT_VERSION
    doc.segment_attempts = outcome.attempts
    doc.sentence_count = outcome.sentence_count
    if outcome.stats.get("word_count"):
        doc.word_count = outcome.stats["word_count"]
    doc.structure_json = None  # 分段变了，旧结构作废

    for result in outcome.runs:
        _record_run(doc.id, "segment", result, model, segmenter.PROMPT_VERSION)

    db.session.commit()

    return {
        "status": outcome.status,
        "attempts": outcome.attempts,
        "sentence_count": outcome.sentence_count,
        "word_count": doc.word_count,
        "model": model,
        "usage": _usage(outcome.runs),
    }


def analyze_structure(doc: Document, client: LLMClient, config) -> dict[str, Any]:
    model = config.LLM_MODEL_ANALYSIS
    rows = (
        db.session.query(Sentence)
        .filter(Sentence.document_id == doc.id)
        .order_by(Sentence.idx)
        .all()
    )
    paragraph_texts: list[list[str]] | None = None
    if doc.segment_status == "segmented" and rows:
        grouped: dict[int, list[str]] = {}
        for row in rows:
            grouped.setdefault(row.para_idx, []).append(row.text)
        paragraph_texts = [grouped[key] for key in sorted(grouped)]

    try:
        structure, result = structure_service.run(
            client,
            raw_text=doc.raw_text,
            paragraph_texts=paragraph_texts,
            target_level=doc.target_level,
            model=model,
        )
    except AppError as exc:
        _record_error(doc.id, "structure", model, structure_service.PROMPT_VERSION, exc)
        raise

    doc.structure_json = structure.model_dump()
    doc.structure_model = result.model
    doc.structure_prompt_version = structure_service.PROMPT_VERSION
    _record_run(doc.id, "structure", result, model, structure_service.PROMPT_VERSION)
    db.session.commit()

    return {
        "genre": structure.genre,
        "sections": len(structure.sections),
        "model": result.model,
        "usage": _usage([result]),
    }


def analyze_sentences(doc: Document, client: LLMClient, config, only_missing: bool = True) -> dict[str, Any]:
    if doc.segment_status != "segmented":
        raise AppError(ErrorCode.STAGE_NOT_ALLOWED, "尚未完成分段，无法逐句精讲", 409)

    model = config.LLM_MODEL_ANALYSIS
    rows = (
        db.session.query(Sentence)
        .filter(Sentence.document_id == doc.id)
        .order_by(Sentence.idx)
        .all()
    )
    todo = [row for row in rows if not row.analyzed] if only_missing else rows
    if not todo:
        return {"batches": 0, "analyzed": 0, "total": len(rows), "usage": _usage([])}

    runs: list[LLMResult] = []
    analyzed = 0
    batch_count = 0

    for group in sentence_service.batched(todo, max(1, config.SENTENCE_BATCH_SIZE)):
        batch_count += 1
        payload = [{"id": row.idx, "text": row.text} for row in group]
        try:
            items, result = sentence_service.analyze_batch(
                client,
                sentences=payload,
                target_level=doc.target_level,
                model=model,
            )
        except AppError as exc:
            _record_error(doc.id, "sentences", model, sentence_service.PROMPT_VERSION, exc)
            db.session.commit()
            raise

        runs.append(result)
        _record_run(doc.id, "sentences", result, model, sentence_service.PROMPT_VERSION)

        by_idx = {row.idx: row for row in group}
        for item in items:
            row = by_idx.get(item.id)
            if row is None:
                continue
            _apply_sentence(row, item, doc.target_level, config)
            analyzed += 1
        db.session.commit()

    return {
        "batches": batch_count,
        "analyzed": analyzed,
        "total": len(rows),
        "usage": _usage(runs),
    }


def _apply_sentence(row: Sentence, item, target_level: str, config) -> None:
    row.translation = item.translation
    row.difficulty = item.difficulty
    row.structure_hint = item.structure_hint
    row.note = item.note
    row.analyzed = True

    for existing in list(row.grammar):
        db.session.delete(existing)
    for existing in list(row.vocab):
        db.session.delete(existing)
    db.session.flush()

    for grammar in item.grammar:
        db.session.add(
            SentenceGrammar(
                sentence_id=row.id,
                label=grammar.label,
                span=grammar.span,
                span_start=grammar.span_start,
                span_end=grammar.span_end,
                explain_cn=grammar.explain_cn,
                exam_tip=grammar.exam_tip,
            )
        )

    for vocab in item.key_vocab:
        tag = lookup(vocab.lemma or vocab.surface, target_level, config.EXAM_TAG_SOURCE)
        if tag.source == "model" and vocab.syllabus_guess in LEVEL_NAMES:
            tag.level = vocab.syllabus_guess
            tag.label = f"{LEVEL_NAMES[vocab.syllabus_guess]}考纲"
        db.session.add(
            SentenceVocab(
                sentence_id=row.id,
                surface=vocab.surface,
                span_start=vocab.span_start,
                span_end=vocab.span_end,
                lemma=vocab.lemma or vocab.surface,
                pos=vocab.pos,
                sense_cn=vocab.sense_cn,
                collocations_json=vocab.collocations,
                pitfall_cn=vocab.pitfall_cn,
                exam_hint=vocab.exam_hint,
                exam_label=tag.label,
                exam_level=tag.level,
                exam_band=tag.band,
                exam_source=tag.source,
            )
        )


def summarize_usage(runs: list[LLMResult]) -> dict[str, Any]:
    input_tokens = sum(r.input_tokens for r in runs)
    output_tokens = sum(r.output_tokens for r in runs)
    cost_usd = sum(r.cost_usd for r in runs)
    return {
        "calls": len(runs),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_usd, 6),
        "latency_ms": sum(r.latency_ms for r in runs),
    }


_usage = summarize_usage


def analyze_document(
    doc: Document,
    client: LLMClient,
    config,
    stages: list[str] | None = None,
) -> dict[str, Any]:
    """按需执行阶段。

    分段失败不抛 500：文档降级为 unsegmented，结构分析仍可运行，
    逐句阶段跳过 —— 这是「不分段只读模式」的服务端实现。
    """
    requested = stages or ["segment", "structure", "sentences"]
    results: dict[str, Any] = {}

    if "segment" in requested and doc.segment_status != "segmented":
        try:
            results["segment"] = segment_document(doc, client, config)
        except AppError as exc:
            results["segment"] = {"status": "failed", "error_code": exc.code, "error_message": exc.message}

    if "structure" in requested:
        try:
            results["structure"] = analyze_structure(doc, client, config)
        except AppError as exc:
            results["structure"] = {"status": "failed", "error_code": exc.code, "error_message": exc.message}

    if "sentences" in requested:
        if doc.segment_status != "segmented":
            results["sentences"] = {"skipped": True, "reason": "尚未完成分段，逐句精讲不可用"}
        else:
            try:
                results["sentences"] = analyze_sentences(doc, client, config)
            except AppError as exc:
                results["sentences"] = {"status": "failed", "error_code": exc.code, "error_message": exc.message}

    results["has_failure"] = any(item.get("status") == "failed" for item in results.values())
    return results
