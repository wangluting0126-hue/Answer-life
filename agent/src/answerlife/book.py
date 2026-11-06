"""答案之书 skill 的程序化入口。

skill 原样放在 skills/answer-book/，仍然可以单独装进任何 AI 客户端使用。这里直接导入它的
scripts/answer_book.py：查引文、校验、渲染、记录、回看全部走 skill 自己的代码，规则只有一份。
"""

from __future__ import annotations

import importlib.util
import re
import uuid
from functools import lru_cache
from pathlib import Path

from answerlife.settings import SKILL_DIR, get_settings

REFERENCE_FILES = ("voice.md", "formula.md", "conversation.md", "themes.md", "page-schema.md", "sources.md", "history.md", "reasoning.md", "reminders.md")


@lru_cache(maxsize=1)
def ab():
    """导入 skill 的 answer_book.py。"""
    path = SKILL_DIR / "scripts" / "answer_book.py"
    spec = importlib.util.spec_from_file_location("answer_book", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def themes() -> tuple[str, ...]:
    return ab().THEMES


@lru_cache(maxsize=1)
def skill_text() -> str:
    """SKILL.md 与参考文档，拼成系统提示词里稳定的一段（可被缓存）。"""
    parts = [(SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")]
    for name in REFERENCE_FILES:
        parts.append(f"\n\n<reference file=\"references/{name}\">\n"
                     + (SKILL_DIR / "references" / name).read_text(encoding="utf-8") + "\n</reference>")
    return "".join(parts)


def search_quotes(theme: str = "", query: str = "", limit: int = 12) -> list[dict]:
    quotes = ab().bank()
    result = []
    for q in quotes.values():
        if theme and theme not in q.get("theme", []):
            continue
        text = q.get("original", "") + q.get("gloss", "") + q.get("work", "") + q.get("chapter", "")
        if query and query not in text and query not in q["id"]:
            continue
        usable = q.get("verified") is True and not q.get("blocked")
        result.append({"id": q["id"], "cite": q.get("cite") or f"《{q['work']}》{q.get('ref', '')}",
                       "original": q["original"], "gloss": q.get("gloss", ""), "theme": q.get("theme", []),
                       "speaker": q.get("speaker", ""), "usable": usable,
                       **({"block_reason": q.get("block_reason", "")} if not usable else {})})
    return result[:limit]


def _slug(title: str) -> str:
    text = re.sub(r"\s+", "", title)[:16]
    text = re.sub(r"[\\/:*?\"<>|。，、！？“”‘’（）()·]", "", text)
    return text or "答案页"


def render(data: dict) -> dict:
    """校验并渲染一页（或 2–3 页的卷宗）。返回文件路径与页面摘要；不合格直接抛 ValueError。"""
    s = get_settings()
    title, pages = ab().document(data)   # 先校验一遍，错误信息原样交回模型改
    first = pages[0]
    page_id = uuid.uuid4().hex[:8]
    out = s.pages_dir / f"{first['date']}-{_slug(title)}-{page_id}.html"
    files = ab().render(data, out)
    return {"id": page_id, "title": title, "file": str(out), "name": out.name, "files": files,
            "url": f"{s.base_url}/pages/{out.name}", "pages": pages,
            "markdown": Path(out.with_suffix(".md")).read_text(encoding="utf-8")}


def record(page: dict) -> dict:
    """获授权后把一页的最少摘要写进 skill 的记录目录（不留整段原话）。"""
    return ab().record(page, get_settings().book_home)


def update(record_id: str, status: str | None = None, result: str | None = None, unchanged: str | None = None) -> dict:
    return ab().update(get_settings().book_home, record_id, status=status, result=result, unchanged=unchanged)


def review(start: str, end: str) -> dict:
    data = ab().review(get_settings().book_home, start, end)
    data.pop("records", None)   # 交给模型时只给统计和每个问题的最近一次，不重复整份记录
    return data
