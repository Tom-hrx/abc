"""应用配置：全部通过环境变量覆盖，默认值即「中考优先」的可用配置。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or (
        f"sqlite:///{(ROOT_DIR / 'data' / 'app.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 64 * 1024 * 1024  # 请求体上限（图片走 multipart，需要比纯文本宽）

    # ---- 图片上传 ----
    MAX_IMAGE_MB = _int("MAX_IMAGE_MB", 10)
    MAX_IMAGE_COUNT = _int("MAX_IMAGE_COUNT", 5)
    ALLOWED_IMAGE_MIMES = ("image/png", "image/jpeg", "image/webp")

    # ---- 产品默认值 ----
    TARGET_LEVEL = os.getenv("TARGET_LEVEL", "zhongkao")  # zhongkao | gaokao
    MAX_DOC_CHARS = _int("MAX_DOC_CHARS", 20000)
    EXAM_TAG_SOURCE = os.getenv("EXAM_TAG_SOURCE", "table")  # table | model | off

    # ---- 模型调用 ----
    LLM_MODE = os.getenv("LLM_MODE", "auto")  # auto | openai | fake
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL_SEGMENT = os.getenv("LLM_MODEL_SEGMENT", "gpt-4o-mini")
    LLM_MODEL_ANALYSIS = os.getenv("LLM_MODEL_ANALYSIS", "gpt-4o-mini")
    LLM_MODEL_VISION = os.getenv("LLM_MODEL_VISION", os.getenv("LLM_MODEL_ANALYSIS", "gpt-4o-mini"))
    LLM_MODEL_POLYSEMY = os.getenv("LLM_MODEL_POLYSEMY", os.getenv("LLM_MODEL_ANALYSIS", "gpt-4o-mini"))
    LLM_CONCURRENCY = _int("LLM_CONCURRENCY", 3)
    LLM_TIMEOUT = _int("LLM_TIMEOUT", 180)
    LLM_MAX_RETRIES = _int("LLM_MAX_RETRIES", 3)
    LLM_TEMPERATURE = _float("LLM_TEMPERATURE", 0.2)
    LLM_MAX_CONTINUATIONS = _int("LLM_MAX_CONTINUATIONS", 3)

    # 美元 / 百万 token，用于成本预估；按实际渠道单价改
    LLM_PRICE_IN_PER_1M = _float("LLM_PRICE_IN_PER_1M", 0.15)
    LLM_PRICE_OUT_PER_1M = _float("LLM_PRICE_OUT_PER_1M", 0.60)
    USD_TO_CNY = _float("USD_TO_CNY", 7.2)

    # ---- 分批 ----
    SENTENCE_BATCH_SIZE = _int("SENTENCE_BATCH_SIZE", 5)

    # 仅本地开发：启动时自动建表（生产用 flask db upgrade）
    AUTO_CREATE_TABLES = os.getenv("AUTO_CREATE_TABLES", "1") == "1"

    # 同步分析接口（POST /documents/{id}/analyze）仅用于 curl 自测，生产应关闭
    ENABLE_SYNC_ANALYZE = os.getenv("ENABLE_SYNC_ANALYZE", "1") == "1"

    # 纯静态前端目录（零构建），由 Flask 直接托管
    WEB_DIR = str(ROOT_DIR / "web")


class ConfigView:
    """服务层用的只读配置视图：同时支持 cfg.X 与 cfg['X']。

    Flask 的 app.config 是 dict，属性访问不可用；服务层统一用这个包装。
    """

    def __init__(self, mapping) -> None:
        self._mapping = mapping

    def __getattr__(self, name: str):
        try:
            return self._mapping[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __getitem__(self, key: str):
        return self._mapping[key]

    def get(self, key: str, default=None):
        return self._mapping.get(key, default)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LLM_MODE = "fake"
    AUTO_CREATE_TABLES = False
