"""陪伴节奏：Agent 主动找你的三件事（借鉴 Syll 的 proactive rituals、wealthpilot 的到期复核）。

- 晚安小结：每天到点，在已配对的 IM 里轻轻问一句今天怎么样（默认关闭，网页“设置”里打开）；
- 未来信：到了送达日期，把信送回来；
- 实验回访：答案页的七天实验到期，问一句做了没有。

都只发给已配对的主人；没有可用 IM 时不标记“已发送”，网页首页照样能看到。
"""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from answerlife.settings import get_settings, today

log = logging.getLogger("answerlife.routines")

DEFAULTS = {"evening_on": False, "evening_time": "21:30", "letters_on": True, "checkin_on": True}


def config(store) -> dict:
    return {**DEFAULTS, **(store.get("routines") or {})}


def update(store, patch: dict) -> dict:
    cfg = config(store)
    for k, v in patch.items():
        if k in DEFAULTS:
            if k == "evening_time":
                dt.time.fromisoformat(str(v))     # 校验 HH:MM
            cfg[k] = v
    store.set("routines", cfg)
    return cfg


def _now() -> dt.datetime:
    try:
        return dt.datetime.now(ZoneInfo(get_settings().timezone))
    except Exception:  # noqa: BLE001
        return dt.datetime.now()


async def _push(bots: dict, text: str) -> bool:
    for bot in bots.values():
        try:
            if await bot.push(text):
                return True
        except Exception as e:  # noqa: BLE001
            log.warning("主动消息发送失败（%s）：%s", bot.channel, e)
    return False


async def tick(store, bots: dict, now: dt.datetime | None = None) -> list[str]:
    """跑一遍，返回这次发出的消息类型。每分钟调用一次。"""
    cfg, now = config(store), now or _now()
    sent: list[str] = []
    day = now.date().isoformat()

    if cfg["letters_on"]:
        for letter in store.due_letters(day):
            title = letter["title"] or "一封信"
            text = (f"{letter['written_on']} 的你，给今天的你写了一封信：「{title}」\n\n{letter['content']}\n\n"
                    "读完想说点什么，直接回我。")
            if await _push(bots, text):
                store.mark_letter_delivered(letter["id"])
                sent.append("letter")

    if cfg["checkin_on"]:
        due_before = (now.date() - dt.timedelta(days=7)).isoformat()
        for page in store.due_checkins(due_before):
            title = page["title"].replace("\n", "")
            text = (f"上回翻到《{title}》，你想试一件事：\n{page['action']}\n\n"
                    "后来试了吗？要是还没顾上，也可以说说那天发生了什么。")
            if await _push(bots, text):
                store.mark_nudged(page["id"])
                sent.append("checkin")

    if cfg["evening_on"] and store.get("routines.evening_last") != day:
        hh, mm = map(int, cfg["evening_time"].split(":"))
        if (now.hour, now.minute) >= (hh, mm):
            text = "今天快结束了。用一个词说说今天？想的话，我们可以一起找找今天的三件小事。"
            if await _push(bots, text):
                sent.append("evening")
            store.set("routines.evening_last", day)     # 没发出去也不在半夜反复重试

    return sent


def home_cards(store) -> dict:
    """网页首页需要的“今天”信息。"""
    d = today()
    letters = store.letters(d)
    due_before = (dt.date.fromisoformat(d) - dt.timedelta(days=7)).isoformat()
    return {"arrived_letters": [x for x in letters["arrived"] if not x.get("read")][:3],
            "sealed_letters": letters["sealed"][:5],
            "due_experiments": [p for p in store.pages(50) if p["date"] <= due_before and not p["nudged"]][:3],
            "routines": config(store)}
