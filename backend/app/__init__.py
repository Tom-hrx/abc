"""应用工厂。生产用 gunicorn 指向 wsgi:app，本地用 flask --app wsgi run。"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from .config import Config
from .errors import register_error_handlers
from .extensions import db, migrate


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.json.ensure_ascii = False

    db.init_app(app)
    migrate.init_app(app, db)

    register_error_handlers(app)

    from .api.v1 import bp as api_v1

    app.register_blueprint(api_v1)

    _register_web(app)

    from .cli import register_cli

    register_cli(app)

    if app.config.get("AUTO_CREATE_TABLES"):
        with app.app_context():
            from . import models  # noqa: F401

            db.create_all()

    return app


def _register_web(app: Flask) -> None:
    """托管 web/ 下的静态前端：/ 给首页，/assets/* 给 CSS 与 JS。"""
    web_dir = Path(app.config["WEB_DIR"])

    @app.get("/")
    def index():
        if not (web_dir / "index.html").exists():
            return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "前端未构建：缺少 web/index.html"}}), 404
        return send_from_directory(web_dir, "index.html")

    @app.get("/assets/<path:filename>")
    def assets(filename: str):
        return send_from_directory(web_dir, filename)

    @app.get("/favicon.ico")
    def favicon():
        return ("", 204)
