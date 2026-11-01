"""统一错误码。客户端只依赖 code 做分支，message 仅供开发期排查。"""
from __future__ import annotations

from typing import Any

from flask import jsonify


class ErrorCode:
    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    DOC_TOO_LARGE = "DOC_TOO_LARGE"
    NO_IMAGE = "NO_IMAGE"
    IMAGE_UNSUPPORTED = "IMAGE_UNSUPPORTED"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    IMAGE_COUNT_EXCEEDED = "IMAGE_COUNT_EXCEEDED"
    SEGMENT_INCOMPLETE = "SEGMENT_INCOMPLETE"
    LLM_BAD_OUTPUT = "LLM_BAD_OUTPUT"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    STAGE_NOT_ALLOWED = "STAGE_NOT_ALLOWED"
    INTERNAL = "INTERNAL"


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra


def ok(data: Any, status: int = 200):
    return jsonify({"ok": True, "data": data}), status


def fail(code: str, message: str, status: int = 400, **extra: Any):
    payload: dict[str, Any] = {"code": code, "message": message}
    if extra:
        payload.update(extra)
    return jsonify({"ok": False, "error": payload}), status


def register_error_handlers(app) -> None:
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(AppError)
    def _app_error(exc: AppError):
        return fail(exc.code, exc.message, exc.status, **exc.extra)

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        code = {
            404: ErrorCode.NOT_FOUND,
            413: ErrorCode.DOC_TOO_LARGE,
        }.get(exc.code or 500, ErrorCode.BAD_REQUEST)
        return fail(code, exc.description or exc.name, exc.code or 500)

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):
        app.logger.exception("unhandled error")
        return fail(ErrorCode.INTERNAL, "服务器内部错误", 500)
