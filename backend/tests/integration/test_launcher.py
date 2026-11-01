"""启动链路回归：CLI 命令、首页 file:// 提示、start.cmd 存在性。

「打不开」这类问题靠单元测试防不住全部，但这几项能挡住最常见的三种：
命令未注册、file:// 直接打开时无提示、启动脚本路径写错。
"""
from pathlib import Path

from app import create_app
from app.cli import _port_in_use

ROOT = Path(__file__).resolve().parents[3]


def test_serve_command_is_registered(app):
    commands = app.cli.list_commands(app.make_shell_context())
    assert "serve" in commands
    assert "import-exam-words" in commands


def test_serve_command_has_host_port_options(app):
    command = app.cli.get_command(app.make_shell_context(), "serve")
    params = {param.name for param in command.params}
    assert {"host", "port", "no_browser"} <= params


def test_port_in_use_detects_closed_port():
    # 用一个几乎不可能被占用的高位端口
    assert _port_in_use("127.0.0.1", 59321) is False


def test_index_html_warns_about_file_protocol(client):
    body = client.get("/").get_data(as_text=True)
    assert "location.protocol" in body
    assert "file:" in body
    assert "start.cmd" in body


def test_start_cmd_exists_and_uses_serve():
    path = ROOT / "start.cmd"
    assert path.exists(), "缺少 start.cmd（双击启动入口）"
    text = path.read_text(encoding="utf-8")
    assert "flask --app wsgi serve" in text
    # 相对路径在 cd 之后会失效；必须使用 %~dp0 绝对路径
    assert "%~dp0.venv\\Scripts\\python.exe" in text
    assert "pause" in text


def test_app_factory_with_default_config_still_builds():
    """默认配置（无 .env）也要能创建应用，否则 start.cmd 会直接失败。"""
    application = create_app()
    client = application.test_client()
    assert client.get("/api/v1/health").status_code == 200
