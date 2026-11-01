from __future__ import annotations

import hashlib
import time

from flask import current_app, request

from ...config import ConfigView
from ...errors import AppError, ErrorCode, ok
from ...extensions import db
from ...models import AnalysisRun, Document, Sentence
from ...services import pipeline, vision as vision_service
from ...services.llm.client import LLMClient
from ...services.llm.cost import estimate_document
from . import bp

_VALID_LEVELS = ("zhongkao", "gaokao")


def _get_document(doc_id: int) -> Document:
    doc = db.session.get(Document, doc_id)
    if doc is None:
        raise AppError(ErrorCode.NOT_FOUND, f"文档 {doc_id} 不存在", 404)
    return doc


@bp.post("/documents")
def create_document():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise AppError(ErrorCode.BAD_REQUEST, "text 不能为空")

    cfg = ConfigView(current_app.config)
    if len(text) > cfg["MAX_DOC_CHARS"]:
        raise AppError(
            ErrorCode.DOC_TOO_LARGE,
            f"文档 {len(text)} 字符，超过 {cfg['MAX_DOC_CHARS']} 字符上限",
            413,
        )

    target_level = payload.get("target_level") or cfg["TARGET_LEVEL"]
    if target_level not in _VALID_LEVELS:
        raise AppError(ErrorCode.BAD_REQUEST, f"target_level 只能是 {_VALID_LEVELS}")

    doc = Document(
        title=payload.get("title"),
        raw_text=text,  # 原样保存，不做任何归一化
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        source=payload.get("source") or "paste",
        target_level=target_level,
        char_count=len(text),
    )
    db.session.add(doc)
    db.session.commit()

    return ok(
        {
            "id": doc.id,
            "title": doc.title,
            "char_count": doc.char_count,
            "target_level": doc.target_level,
            "segment_status": doc.segment_status,
            "estimate": estimate_document(doc.char_count, cfg),
        },
        201,
    )


@bp.post("/documents/from-image")
def create_document_from_image():
    """图片 → 视觉模型转写 → 建文档。字段名固定 file，便于小程序 wx.uploadFile。"""
    files = [f for f in request.files.getlist("file") if f and f.filename]
    if not files:
        raise AppError(ErrorCode.NO_IMAGE, "请至少上传一张文章图片（字段名 file）")

    cfg = ConfigView(current_app.config)
    if len(files) > cfg.MAX_IMAGE_COUNT:
        raise AppError(
            ErrorCode.IMAGE_COUNT_EXCEEDED,
            f"一次最多 {cfg.MAX_IMAGE_COUNT} 张图片，当前 {len(files)} 张",
        )

    target_level = request.form.get("target_level") or cfg["TARGET_LEVEL"]
    if target_level not in _VALID_LEVELS:
        raise AppError(ErrorCode.BAD_REQUEST, f"target_level 只能是 {_VALID_LEVELS}")

    images: list[bytes] = []
    mimes: list[str] = []
    limit_bytes = cfg.MAX_IMAGE_MB * 1024 * 1024
    for upload in files:
        mime = (upload.mimetype or "").lower()
        if mime not in cfg.ALLOWED_IMAGE_MIMES:
            raise AppError(
                ErrorCode.IMAGE_UNSUPPORTED,
                f"不支持的图片格式：{mime or upload.filename}（仅支持 PNG / JPG / WEBP）",
                415,
            )
        data = upload.read()
        if not data:
            raise AppError(ErrorCode.IMAGE_UNSUPPORTED, f"{upload.filename} 是空文件", 415)
        if len(data) > limit_bytes:
            raise AppError(
                ErrorCode.IMAGE_TOO_LARGE,
                f"{upload.filename} 超过 {cfg.MAX_IMAGE_MB}MB 上限",
                413,
            )
        images.append(data)
        mimes.append(mime)

    client = LLMClient(cfg)
    vision = vision_service.extract(
        client,
        images=images,
        mimes=mimes,
        model=cfg.LLM_MODEL_VISION,
    )

    text = vision.text
    if len(text) > cfg.MAX_DOC_CHARS:
        raise AppError(
            ErrorCode.DOC_TOO_LARGE,
            f"识别出的正文 {len(text)} 字符，超过 {cfg.MAX_DOC_CHARS} 字符上限，请拆成多篇",
            413,
        )

    title = request.form.get("title") or vision.title
    doc = Document(
        title=title,
        raw_text=text,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        source="image",
        target_level=target_level,
        char_count=len(text),
        source_meta_json={
            "pages": len(images),
            "complete": vision.complete,
            "notes": vision.notes,
            "page_chars": [len(page.text) for page in vision.pages],
        },
        extraction_model=cfg.LLM_MODEL_VISION,
        extraction_prompt_version=vision_service.PROMPT_VERSION,
    )
    db.session.add(doc)
    db.session.flush()

    started_summary = pipeline.summarize_usage(vision.runs)
    for result in vision.runs:
        db.session.add(
            AnalysisRun(
                document_id=doc.id,
                stage="vision",
                model=result.model,
                prompt_version=vision_service.PROMPT_VERSION,
                ok=True,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=result.cost_usd,
                latency_ms=result.latency_ms,
            )
        )
    db.session.commit()

    return ok(
        {
            "id": doc.id,
            "title": doc.title,
            "char_count": doc.char_count,
            "target_level": doc.target_level,
            "segment_status": doc.segment_status,
            "source": doc.source,
            "extraction": {
                "text": doc.raw_text,
                "pages": len(images),
                "complete": vision.complete,
                "notes": vision.notes,
                "model": cfg.LLM_MODEL_VISION,
                "prompt_version": vision_service.PROMPT_VERSION,
            },
            "estimate": estimate_document(doc.char_count, cfg),
            "usage": started_summary,
        },
        201,
    )


@bp.get("/documents")
def list_documents():
    page = max(1, request.args.get("page", default=1, type=int))
    page_size = min(50, max(1, request.args.get("page_size", default=20, type=int)))
    query = db.session.query(Document).order_by(Document.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return ok(
        {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [row.to_meta() for row in rows],
        }
    )


@bp.get("/documents/<int:doc_id>")
def get_document(doc_id: int):
    return ok(_get_document(doc_id).to_meta())


@bp.get("/documents/<int:doc_id>/sentences")
def list_sentences(doc_id: int):
    doc = _get_document(doc_id)
    page = max(1, request.args.get("page", default=1, type=int))
    page_size = min(200, max(1, request.args.get("page_size", default=50, type=int)))
    query = (
        db.session.query(Sentence)
        .filter(Sentence.document_id == doc.id)
        .order_by(Sentence.idx)
    )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return ok(
        {
            "document_id": doc.id,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [row.to_dict() for row in rows],
        }
    )


@bp.get("/documents/<int:doc_id>/runs")
def list_runs(doc_id: int):
    """模型调用账本：用于核对成本（G7）和排查失败阶段。"""
    doc = _get_document(doc_id)
    rows = (
        db.session.query(AnalysisRun)
        .filter(AnalysisRun.document_id == doc.id)
        .order_by(AnalysisRun.id)
        .all()
    )
    return ok(
        {
            "document_id": doc.id,
            "items": [
                {
                    "id": row.id,
                    "stage": row.stage,
                    "ok": row.ok,
                    "model": row.model,
                    "prompt_version": row.prompt_version,
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                    "cost_usd": row.cost_usd,
                    "latency_ms": row.latency_ms,
                    "error_code": row.error_code,
                    "error_message": row.error_message,
                }
                for row in rows
            ],
            "total": {
                "calls": len(rows),
                "input_tokens": sum(row.input_tokens or 0 for row in rows),
                "output_tokens": sum(row.output_tokens or 0 for row in rows),
                "cost_usd": round(sum(row.cost_usd or 0 for row in rows), 6),
            },
        }
    )


@bp.post("/documents/<int:doc_id>/analyze")
def analyze_document(doc_id: int):
    """同步分析（仅开发/自测）。生产走 M2 的任务化接口。"""
    if not current_app.config["ENABLE_SYNC_ANALYZE"]:
        raise AppError(ErrorCode.STAGE_NOT_ALLOWED, "同步分析接口未启用，请使用任务接口", 403)

    doc = _get_document(doc_id)
    payload = request.get_json(silent=True) or {}
    requested = payload.get("stages")
    allowed = {"segment", "structure", "sentences"}
    if requested is not None:
        if not isinstance(requested, list) or not set(requested) <= allowed:
            raise AppError(ErrorCode.BAD_REQUEST, f"stages 只能取 {sorted(allowed)} 的子集")

    cfg = ConfigView(current_app.config)
    client = LLMClient(cfg)
    started = time.perf_counter()
    stages = pipeline.analyze_document(doc, client, cfg, requested)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    db.session.expire_all()
    doc = _get_document(doc_id)
    return ok(
        {
            "document": doc.to_meta(),
            "stages": stages,
            "elapsed_ms": elapsed_ms,
            "llm_mode": client.mode,
        }
    )


@bp.post("/documents/<int:doc_id>/segment")
def resegment_document(doc_id: int):
    payload = request.get_json(silent=True) or {}
    if payload.get("confirm") is not True:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "重新分段会作废已有的逐句讲解，请在请求体中传 confirm: true",
            409,
        )

    doc = _get_document(doc_id)
    cfg = ConfigView(current_app.config)
    client = LLMClient(cfg)
    result = pipeline.segment_document(doc, client, cfg)
    db.session.expire_all()
    doc = _get_document(doc_id)
    return ok({"segment": result, "document": doc.to_meta()})
