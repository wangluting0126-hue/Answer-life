"""答案之书的工具：对应 skill 里 scripts/answer_book.py 的 quotes / render / record / update / review。"""

from __future__ import annotations

import json

from answerlife import book, voice

SKILL = "answer-book"

SPECS = [
    {"name": "search_quotes",
     "description": "答案之书：在公版引文库里查候选原文。按主题筛，可加关键词。只有 usable=true 的才能作为 quote_id / dissent_quote_id。",
     "input_schema": {"type": "object", "properties": {
         "theme": {"type": "string", "enum": list(book.themes())},
         "query": {"type": "string", "description": "原文、作品或 id 里的关键词，可空"}}, "required": []}},
    {"name": "create_answer_page",
     "description": ("答案之书：生成答案页（HTML + Markdown）。page 为 page-schema 1.1 JSON：单页对象，或卷宗 "
                     "{chapter_title, pages:[2-3 页]}。校验失败会返回原因，改好后重试。已获记忆同意时自动写实验记录。"),
     "input_schema": {"type": "object", "properties": {"page": {"type": "object"}}, "required": ["page"]}},
    {"name": "update_experiment",
     "description": "答案之书：按用户回报更新某次七天实验（状态、结果、行为是否仍未改变）。只写用户明确说过的。",
     "input_schema": {"type": "object", "properties": {
         "record_id": {"type": "string"},
         "status": {"type": "string", "enum": ["unknown", "planned", "done", "skipped"]},
         "result": {"type": "string"},
         "unchanged": {"type": "string", "enum": ["yes", "no", "unknown"]}}, "required": ["record_id"]}},
    {"name": "review_records",
     "description": "答案之书：统计闭区间日期内已保存的实验记录（周/月回看），附同期情绪打卡与日记数量。",
     "input_schema": {"type": "object", "properties": {
         "start": {"type": "string", "description": "YYYY-MM-DD"},
         "end": {"type": "string", "description": "YYYY-MM-DD"}}, "required": ["start", "end"]}},
]


def search_quotes(ctx, theme: str = "", query: str = "") -> dict:
    return {"quotes": book.search_quotes(theme, query)}


def create_answer_page(ctx, page: dict) -> dict:
    if isinstance(page, str):
        page = json.loads(page)
    page = voice.page_copy(page)
    rendered = book.render(page)
    raw_pages = page["pages"] if "pages" in page else [page]
    record_ids = [book.record(p)["id"] for p in raw_pages] if ctx.store.consent() is True else []
    first = rendered["pages"][0]
    ctx.store.add_page({"id": rendered["id"], "conv_id": ctx.conv_id, "date": first["date"], "title": rendered["title"],
                        "theme": first["theme"], "issue_key": first["issue_key"], "action": first["action"],
                        "criterion": first["criterion"], "file": rendered["name"],
                        "record_id": record_ids[0] if record_ids else ""})
    summary = {"title": rendered["title"], "url": rendered["url"], "criterion": first["criterion"],
               "action": first["action"], "path": rendered["file"]}
    ctx.pages.append(summary)
    ctx.emit("page", **summary)
    return {"ok": True, "url": rendered["url"], "record_ids": record_ids, "recorded": bool(record_ids),
            "note": "这一页写好了。把链接给对方，可以顺手提一句这周要试的事。"}


def update_experiment(ctx, record_id: str, status=None, result=None, unchanged=None) -> dict:
    if ctx.store.consent() is not True:
        return {"error": "用户没有同意保存记录，无法更新。"}
    return {"ok": True, "record": book.update(record_id, status=status, result=result, unchanged=unchanged)}


def review_records(ctx, start: str, end: str) -> dict:
    data = book.review(start, end)
    data["moods"] = ctx.store.moods(start, end)
    data["journal_count"] = sum(1 for j in ctx.store.journal(500) if start <= j["date"] <= end)
    return data
