"""命令行入口：启动服务、词表导入与自检。"""
from __future__ import annotations

import json
import socket
import threading
import webbrowser

import click

from .extensions import db
from .services.examdict import importer


def _port_in_use(host: str, port: int) -> bool:
    """Windows 上 SO_REUSEADDR 允许重复绑定，所以用「能否连上」判断更可靠。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def register_cli(app) -> None:
    @app.cli.command("serve")
    @click.option("--host", default="127.0.0.1", show_default=True)
    @click.option("--port", default=5000, show_default=True)
    @click.option("--no-browser", is_flag=True, help="不自动打开浏览器")
    def serve(host: str, port: int, no_browser: bool):
        """启动开发服务器（bind 成功后自动打开浏览器）。"""
        from werkzeug.serving import make_server

        if _port_in_use(host, port):
            click.echo(f"[错误] 端口 {port} 已被占用。换一个端口，例如：", err=True)
            click.echo(f"       python -m flask --app wsgi serve --port {port + 1}", err=True)
            click.echo("       或者结束占用该端口的进程后重试。", err=True)
            raise SystemExit(1)

        url = f"http://{host}:{port}/"
        try:
            server = make_server(host, port, app, threaded=True)
        except OSError as exc:
            click.echo(f"[错误] 启动失败：{exc}", err=True)
            raise SystemExit(1) from exc

        click.echo("")
        click.echo("  ==========================================")
        click.echo(f"   英语精读教练已启动")
        click.echo(f"   {url}")
        click.echo("   保持这个窗口开着；按 Ctrl+C 停止服务")
        click.echo("  ==========================================")
        click.echo("")

        if not no_browser:
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            click.echo("\n已停止。")

    @app.cli.command("import-exam-words")
    @click.argument("csv_path")
    @click.option("--source", default=None, help="覆盖 CSV 里的 source 列")
    def import_exam_words(csv_path: str, source: str | None):
        """导入考点词表 CSV（幂等，重复导入会更新）。"""
        with app.app_context():
            result = importer.import_csv(csv_path, source=source)
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))

    @app.cli.command("exam-words")
    @click.option("--limit", default=20, show_default=True)
    def exam_words(limit: int):
        """查看已导入的词表样本。"""
        with app.app_context():
            click.echo(json.dumps(importer.dump_rows(limit), ensure_ascii=False, indent=2))

    @app.cli.command("reset-db")
    @click.option("--yes", is_flag=True, help="确认删除所有表并重建")
    def reset_db(yes: bool):
        """重建表结构（开发用，会清空数据）。"""
        if not yes:
            raise click.UsageError("需要 --yes 确认")
        with app.app_context():
            db.drop_all()
            db.create_all()
        click.echo("数据库已重建")
