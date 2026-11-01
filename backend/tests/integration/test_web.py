"""前端入口必须可访问：这是「进不去程序」的直接回归测试。"""
import pytest


@pytest.mark.parametrize(
    "path,needle",
    [
        ("/", "英语精读教练"),
        ("/", "dropzone"),
        ("/assets/css/app.css", "--cyan"),
        ("/assets/css/app.css", ".dropzone"),
        ("/assets/js/app.js", "api.fromImage"),
        ("/assets/js/upload.js", "createUploader"),
        ("/assets/js/api.js", "/api/v1"),
        ("/assets/js/api.js", "documents/from-image"),
        ("/assets/js/dom.js", "renderHighlighted"),
    ],
)
def test_web_entry_is_served(client, path, needle):
    response = client.get(path)
    assert response.status_code == 200, path
    body = response.get_data(as_text=True)
    assert needle in body, f"{path} 内容异常：缺少 {needle}"
    response.close()


def test_missing_asset_returns_404(client):
    response = client.get("/assets/css/not-exist.css")
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_api_paths_not_shadowed_by_assets(client):
    """静态资源路由不能抢走 API 路径。"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
