from flask import current_app

from ...config import ConfigView
from ...errors import ok
from ...extensions import db
from ...models import ExamWord
from ...services.llm.client import LLMClient
from . import bp


@bp.get("/health")
def health():
    client = LLMClient(ConfigView(current_app.config))
    return ok(
        {
            "status": "ok",
            "llm_mode": client.mode,
            "target_level": current_app.config["TARGET_LEVEL"],
            "exam_tag_source": current_app.config["EXAM_TAG_SOURCE"],
            "exam_words": db.session.query(ExamWord).count(),
        }
    )
