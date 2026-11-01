"""提示词加载：文件内用 @@SYSTEM@@ / @@USER@@ 分隔，{{VAR}} 做占位替换。"""
from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> tuple[str, str]:
    raw = (PROMPT_DIR / name).read_text(encoding="utf-8")
    system_part, _, user_part = raw.partition("@@USER@@")
    system = system_part.replace("@@SYSTEM@@", "", 1).strip()
    return system, user_part.strip()


def render(template: str, **values: object) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template
