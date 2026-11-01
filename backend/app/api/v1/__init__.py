from flask import Blueprint

bp = Blueprint("v1", __name__, url_prefix="/api/v1")

from . import documents, health  # noqa: E402,F401  (需在 bp 定义之后导入)
