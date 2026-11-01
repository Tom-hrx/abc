"""M1 冒烟：图片/文本 → 分析 → 读回结果。

用法：
    python scripts/smoke.py                       # 用 data/samples/demo_page.png
    python scripts/smoke.py --image path/to/p.jpg # 指定图片（可重复传 --image）
    python scripts/smoke.py --text                # 走纯文本接口
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTICLE = ROOT / "data" / "samples" / "demo_article.txt"
DEFAULT_IMAGE = ROOT / "data" / "samples" / "demo_page.png"


def _read(method: str, url: str, *, data: bytes | None = None, headers: dict | None = None, timeout: int = 600) -> dict:
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {url}\n{body}") from exc
    parsed = json.loads(body)
    if not parsed.get("ok"):
        raise SystemExit(f"业务错误 {url}\n{json.dumps(parsed, ensure_ascii=False, indent=2)}")
    return parsed["data"]


def post_json(url: str, payload: dict, timeout: int = 600) -> dict:
    return _read(
        "POST",
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=timeout,
    )


def post_files(url: str, paths: list[Path], fields: dict[str, str], timeout: int = 600) -> dict:
    """手写 multipart，避免额外依赖。"""
    boundary = f"----smoke{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(f"{value}\r\n".encode())
    for path in paths:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode()
        )
        chunks.append(f"Content-Type: {mime}\r\n\r\n".encode())
        chunks.append(path.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    return _read(
        "POST",
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=timeout,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--image", action="append", default=None, help="可重复，最多 5 张")
    parser.add_argument("--text", action="store_true", help="改走文本接口")
    parser.add_argument("--level", default="zhongkao", choices=["zhongkao", "gaokao"])
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("[1/4] 健康检查")
    health = _read("GET", f"{base}/api/v1/health", timeout=30)
    print(f"      llm_mode={health['llm_mode']} target_level={health['target_level']} exam_words={health['exam_words']}")

    print("[2/4] 创建文档")
    if args.text:
        text = ARTICLE.read_text(encoding="utf-8")
        created = post_json(f"{base}/api/v1/documents", {"text": text, "target_level": args.level}, timeout=60)
        print(f"      文本模式 chars={created['char_count']}")
    else:
        paths = [Path(p) for p in (args.image or [str(DEFAULT_IMAGE)])]
        missing = [str(p) for p in paths if not p.exists()]
        if missing:
            raise SystemExit(f"找不到图片：{missing}")
        created = post_files(
            f"{base}/api/v1/documents/from-image",
            paths,
            {"target_level": args.level},
        )
        extraction = created["extraction"]
        print(f"      图片模式 {created['extraction']['pages']} 张 → {created['char_count']} 字符")
        print(f"      识别备注：{extraction['notes'] or '无'}")
        preview = extraction["text"].strip().replace("\n", " ")[:80]
        print(f"      识别预览：{preview}…")

    doc_id = created["id"]
    estimate = created["estimate"]
    print(f"      id={doc_id} 预估={estimate['estimated_cost_cny']} 元 / {estimate['estimated_seconds']} 秒")

    print("[3/4] 同步分析（segment → structure → sentences）")
    analyzed = post_json(f"{base}/api/v1/documents/{doc_id}/analyze", {})
    stages = analyzed["stages"]
    print(f"      segment: {stages['segment']['sentence_count']} 句 / {stages['segment']['attempts']} 次调用")
    print(f"      structure: genre={stages['structure']['genre']} sections={stages['structure']['sections']}")
    print(f"      sentences: {stages['sentences']['analyzed']}/{stages['sentences']['total']} 已精讲，{stages['sentences']['batches']} 批")
    print(f"      耗时 {analyzed['elapsed_ms']} ms，模式 {analyzed['llm_mode']}")

    print("[4/4] 读回前 3 句")
    page = _read("GET", f"{base}/api/v1/documents/{doc_id}/sentences?page=1&page_size=3", timeout=60)
    for row in page["items"]:
        print(f"      [{row['idx']}] {row['text']}")
        print(f"           译文：{row['translation']}")
        if row.get("structure_hint"):
            print(f"           骨架：{row['structure_hint']}")
        for vocab in row["vocab"]:
            tag = vocab["exam_label"] or "无标签"
            print(f"           词：{vocab['surface']} = {vocab['sense_cn']}  [{tag}]")
        for grammar in row["grammar"]:
            print(f"           语法：{grammar['label']} — {grammar['explain_cn']}")

    print()
    print(f"冒烟通过：文档 {doc_id}")
    print(f"完整数据：{base}/api/v1/documents/{doc_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

