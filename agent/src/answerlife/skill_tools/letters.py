"""写给未来的信：封存一封信，到日子由 Agent 送回（IM 推送 + 网页首页）。"""

from __future__ import annotations

import datetime as dt

from answerlife.settings import today

SKILL = "future-letter"

SPECS = [
    {"name": "seal_letter",
     "description": "写给未来的信：封存用户确认过的信，到 deliver_on 那天送回给他。内容必须是用户自己的话或他确认过的整理稿。",
     "input_schema": {"type": "object", "properties": {
         "deliver_on": {"type": "string", "description": "YYYY-MM-DD，必须晚于今天，最多 5 年"},
         "title": {"type": "string", "description": "信封上的一句话"},
         "content": {"type": "string"}}, "required": ["deliver_on", "content"]}},
    {"name": "list_letters",
     "description": "写给未来的信：列出已送达的信（可读全文）和还封着的信（只有日期和标题）。",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
]


def seal_letter(ctx, deliver_on: str, content: str, title: str = "") -> dict:
    day, now = dt.date.fromisoformat(deliver_on), dt.date.fromisoformat(today())
    if day <= now:
        raise ValueError("送达日期需要晚于今天")
    if day > now + dt.timedelta(days=366 * 5):
        raise ValueError("最多封存 5 年")
    lid = ctx.store.add_letter(today(), deliver_on, title.strip(), content.strip(), ctx.conv_id)
    ctx.emit("letter", id=lid, deliver_on=deliver_on, title=title)
    return {"ok": True, "id": lid, "deliver_on": deliver_on,
            "note": "信已封好。告诉用户哪天会送回，并说明需要 answerlife 在那天运行着（IM 推送），否则下次打开网页时在首页出现。"}


def list_letters(ctx) -> dict:
    data = ctx.store.letters(today())
    data["arrived"] = [{k: v for k, v in x.items() if k != "conv_id"} for x in data["arrived"]]
    return data
