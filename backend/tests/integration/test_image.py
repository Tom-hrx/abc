"""图片上传 → 视觉模型转写 → 建文档（夹具模式）。"""
import base64
import io

import pytest

from app.extensions import db
from app.models import AnalysisRun, Document

# 1x1 透明 PNG，够用来验证格式校验与 multipart 链路
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _post(client, files, data=None):
    payload = {"file": [(io.BytesIO(content), name, mime) for name, mime, content in files]}
    payload.update(data or {})
    return client.post("/api/v1/documents/from-image", data=payload, content_type="multipart/form-data")


def test_upload_creates_document_from_image(app, client):
    response = _post(client, [("page1.png", "image/png", PNG_1PX)])
    assert response.status_code == 201, response.get_json()

    data = response.get_json()["data"]
    assert data["source"] == "image"
    assert data["char_count"] > 0
    assert data["segment_status"] == "pending"
    assert data["extraction"]["pages"] == 1
    assert data["extraction"]["text"].startswith("Many students think")

    doc = db.session.get(Document, data["id"])
    assert doc.raw_text == data["extraction"]["text"]
    assert doc.source_meta_json["pages"] == 1

    runs = db.session.query(AnalysisRun).filter_by(document_id=doc.id, stage="vision").all()
    assert len(runs) == 1


def test_upload_then_full_pipeline(app, client):
    created = _post(client, [("page1.png", "image/png", PNG_1PX)]).get_json()["data"]
    doc_id = created["id"]

    response = client.post(f"/api/v1/documents/{doc_id}/analyze")
    assert response.status_code == 200, response.get_json()
    stages = response.get_json()["data"]["stages"]
    assert stages["segment"]["sentence_count"] == 10
    assert stages["sentences"]["analyzed"] == 10


def test_multiple_images_do_not_duplicate_text(app, client):
    """夹具只为第一张返回文本，避免多图时正文重复。"""
    one = _post(client, [("a.png", "image/png", PNG_1PX)]).get_json()["data"]
    two = _post(
        client,
        [("a.png", "image/png", PNG_1PX), ("b.png", "image/png", PNG_1PX)],
    ).get_json()["data"]

    assert two["extraction"]["pages"] == 2
    assert two["char_count"] == one["char_count"]
    assert two["extraction"]["notes"]


def test_missing_file_returns_no_image(client):
    response = client.post("/api/v1/documents/from-image", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "NO_IMAGE"


def test_unsupported_type_is_rejected(client):
    response = _post(client, [("notes.txt", "text/plain", b"just text")])
    assert response.status_code == 415
    assert response.get_json()["error"]["code"] == "IMAGE_UNSUPPORTED"


def test_too_many_images_is_rejected(client):
    files = [(f"{i}.png", "image/png", PNG_1PX) for i in range(6)]
    response = _post(client, files)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "IMAGE_COUNT_EXCEEDED"


def test_oversized_image_is_rejected(app, client):
    app.config["MAX_IMAGE_MB"] = 0
    response = _post(client, [("big.png", "image/png", PNG_1PX)])
    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "IMAGE_TOO_LARGE"


def test_target_level_from_form_is_applied(client):
    response = _post(client, [("a.png", "image/png", PNG_1PX)], data={"target_level": "gaokao"})
    assert response.status_code == 201
    assert response.get_json()["data"]["target_level"] == "gaokao"


def test_invalid_target_level_is_rejected(client):
    response = _post(client, [("a.png", "image/png", PNG_1PX)], data={"target_level": "cet4"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "BAD_REQUEST"
