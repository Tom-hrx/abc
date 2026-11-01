from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class VisionResult(BaseModel):
    """图片转写结果。text 是模型的原始转写，服务端不做任何后处理。"""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    text: str = ""
    complete: bool = True
    notes: str | None = None
