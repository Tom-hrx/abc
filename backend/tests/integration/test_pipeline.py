"""端到端（假模型）：导入词表 → 建文档 → 同步分析 → 校验落库内容。"""
from app.extensions import db
from app.models import Document, ExamWord, Sentence
from app.services.examdict import importer


def _create_document(client, text, level="zhongkao"):
    response = client.post("/api/v1/documents", json={"text": text, "target_level": level})
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def test_health(client):
    payload = client.get("/api/v1/health").get_json()
    assert payload["ok"] is True
    assert payload["data"]["llm_mode"] == "fake"


def test_full_pipeline_with_fake_model(app, client, demo_text):
    db.session.add(
        ExamWord(lemma="address", pos="v.", level="zhongkao", band="high", years_json=[], papers_json=[], source="test")
    )
    db.session.add(
        ExamWord(lemma="mean", pos="v.", level="zhongkao", band="high", years_json=[], papers_json=[], source="test")
    )
    db.session.commit()

    created = _create_document(client, demo_text)
    doc_id = created["id"]
    assert created["estimate"]["estimated_cost_cny"] >= 0
    assert created["segment_status"] == "pending"

    analyzed = client.post(f"/api/v1/documents/{doc_id}/analyze")
    assert analyzed.status_code == 200, analyzed.get_json()
    data = analyzed.get_json()["data"]

    assert data["stages"]["segment"]["sentence_count"] == 10
    assert data["stages"]["sentences"]["analyzed"] == 10
    assert data["document"]["segment_status"] == "segmented"
    assert data["document"]["structure"]["genre"] == "argumentative"

    doc = db.session.get(Document, doc_id)
    sentences = (
        db.session.query(Sentence).filter(Sentence.document_id == doc_id).order_by(Sentence.idx).all()
    )
    assert len(sentences) == 10
    assert all(row.translation for row in sentences)

    # 每个高亮区间必须能在该句内切出 surface（替身按 surface 反查写入）
    for row in sentences:
        for vocab in row.vocab:
            assert row.text[vocab.span_start : vocab.span_end] == vocab.surface

    # 词表命中与否的分支
    labels = {v.surface: v.exam_label for row in sentences for v in row.vocab}
    assert labels["address"] == "中考考纲·高频"
    assert labels["shape"] is None


def test_document_too_large_is_rejected(client):
    response = client.post("/api/v1/documents", json={"text": "a" * 20001})
    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "DOC_TOO_LARGE"


def test_empty_text_is_rejected(client):
    response = client.post("/api/v1/documents", json={"text": "   "})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "BAD_REQUEST"


def test_resegment_requires_confirmation(client, demo_text):
    doc_id = _create_document(client, demo_text)["id"]
    response = client.post(f"/api/v1/documents/{doc_id}/segment", json={})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "BAD_REQUEST"


def test_sentences_pagination(client, demo_text):
    doc_id = _create_document(client, demo_text)["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze")

    response = client.get(f"/api/v1/documents/{doc_id}/sentences?page=1&page_size=4")
    payload = response.get_json()["data"]
    assert payload["total"] == 10
    assert len(payload["items"]) == 4
    assert payload["items"][0]["idx"] == 1


def test_import_csv_is_idempotent(app):
    from pathlib import Path

    csv_path = Path(__file__).resolve().parents[3] / "data" / "exam_words" / "zhongkao_sample.csv"
    first = importer.import_csv(csv_path)
    second = importer.import_csv(csv_path)
    assert first["created"] > 0
    assert second["created"] == 0
    assert second["updated"] == first["created"]
    assert ExamWord.query.filter_by(lemma="address").count() == 1


def test_segment_failure_degrades_to_readonly_with_structure(app, client, demo_text, monkeypatch):
    """分段失败不能 500：降级为不分段只读模式，结构分析仍可用（G10）。"""
    from app.errors import AppError, ErrorCode
    from app.services.llm.client import LLMClient

    original = LLMClient.chat_json

    def patched(self, *, kind, system, user, model, max_tokens=4096, context=None):
        if kind == "segment":
            raise AppError(ErrorCode.SEGMENT_INCOMPLETE, "模拟分段失败", 502)
        return original(
            self, kind=kind, system=system, user=user, model=model, max_tokens=max_tokens, context=context
        )

    monkeypatch.setattr(LLMClient, "chat_json", patched)

    doc_id = _create_document(client, demo_text)["id"]
    response = client.post(f"/api/v1/documents/{doc_id}/analyze")

    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["stages"]["segment"]["status"] == "failed"
    assert data["stages"]["segment"]["error_code"] == "SEGMENT_INCOMPLETE"
    assert data["stages"]["sentences"]["skipped"] is True
    assert data["stages"]["has_failure"] is True
    assert data["document"]["segment_status"] == "unsegmented"
    # 不分段时结构分析仍要能出来
    assert data["document"]["structure"]["genre"] == "argumentative"


def test_stage_filter_runs_only_requested_stage(client, demo_text):
    doc_id = _create_document(client, demo_text)["id"]
    response = client.post(f"/api/v1/documents/{doc_id}/analyze", json={"stages": ["structure"]})
    assert response.status_code == 200, response.get_json()
    stages = response.get_json()["data"]["stages"]
    assert "segment" not in stages
    assert stages["structure"]["genre"] == "argumentative"


def test_invalid_stage_name_is_rejected(client, demo_text):
    doc_id = _create_document(client, demo_text)["id"]
    response = client.post(f"/api/v1/documents/{doc_id}/analyze", json={"stages": ["polysemy"]})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "BAD_REQUEST"


def test_usage_ledger_records_every_call(client, demo_text):
    from app.models import AnalysisRun

    doc_id = _create_document(client, demo_text)["id"]
    client.post(f"/api/v1/documents/{doc_id}/analyze")

    payload = client.get(f"/api/v1/documents/{doc_id}/runs").get_json()["data"]
    stages = [row["stage"] for row in payload["items"]]
    assert stages.count("segment") == 1
    assert stages.count("structure") == 1
    assert stages.count("sentences") == 2  # 10 句 / 每批 5 句
    assert payload["total"]["calls"] == 4
    assert AnalysisRun.query.filter_by(document_id=doc_id).count() == 4
