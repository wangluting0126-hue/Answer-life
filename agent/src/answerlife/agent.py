"""Agent：终端、网页、IM 共用的一轮对话。

一轮的顺序：存下用户的话 → 安全层先看（危机时先发固定求助信息）→ 组系统提示词（SOUL + skill + 记忆）
→ 模型跑工具循环 → 存下回复。模型不可用时，安全信息照样发出，其余如实说明。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from answerlife import llm, safety, soul, voice
from answerlife import skills as registry
from answerlife.settings import get_settings, today
from answerlife.store import Store
from answerlife.tools import ToolContext, specs_for

log = logging.getLogger("answerlife.agent")
NOTE_EVENTS = ("memory", "mood", "journal", "letter", "consent", "skill")


@dataclass
class Reply:
    text: str
    conv_id: str
    safety: str = "none"
    safety_message: str = ""
    pages: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    provider: str = ""
    error: str = ""

    def full_text(self) -> str:
        return "\n\n".join(t for t in (self.safety_message, self.text) if t)


class Agent:
    def __init__(self, store: Store) -> None:
        self.store = store
        self._locks: dict[str, threading.Lock] = {}

    def _lock(self, cid: str) -> threading.Lock:
        return self._locks.setdefault(cid, threading.Lock())

    def respond(self, conv_id: str | None, text: str, channel: str = "cli", skill: str | None = None) -> Reply:
        s = get_settings()
        if not conv_id or not self.store.conversation(conv_id):
            conv_id = self.store.new_conversation(channel)
        if skill and skill in registry.enabled(self.store):
            registry.activate(self.store, conv_id, skill)
        with self._lock(conv_id):
            check = safety.assess(text)
            self.store.add_message(conv_id, "user", text, {"safety": check.level})
            safety_message = safety.FIXED_REPLY.get(check.level, "")

            ctx = ToolContext(self.store, conv_id)
            if safety_message:
                ctx.emit("safety", level=check.level, message=safety_message)
            history = [{"role": m["role"], "content": m["content"]}
                       for m in self.store.messages(conv_id, limit=s.history_turns)]
            while history and history[0]["role"] != "user":
                history.pop(0)
            import datetime as dt
            start = (dt.date.fromisoformat(today()) - dt.timedelta(days=13)).isoformat()
            dynamic = soul.dynamic_prompt(
                date=today(), channel=channel, consent=self.store.consent(), memories=self.store.memories(),
                open_pages=self.store.pages(5), moods=self.store.moods(start, today()),
                safety_note=safety.PROMPT_ADDENDUM.get(check.level, ""))
            enabled = set(registry.enabled(self.store))
            tools = specs_for(enabled, urgent=check.urgent)     # 安全模式下不出页、不布置练习
            blocks = [(soul.static_prompt(self.store), True), (soul.active_prompt(self.store, conv_id), True),
                      (dynamic, False)]
            error = ""
            try:
                result = llm.run(blocks, history, tools, ctx.run)
                answer, provider = voice.polish(result.text), f"{result.provider}:{result.model}"
                if answer == llm.EMPTY and ctx.pages:       # 模型只顾着调工具没说话：至少把出好的页交代清楚
                    p = ctx.pages[-1]
                    answer = f"这一页写好了，翻开看看。\n{p['url']}"
            except llm.LLMError as e:
                log.warning("模型不可用：%s", e)
                error = str(e)
                provider = ""
                answer = ("（我这边暂时连不上模型，没法好好回你。）" if safety_message else
                          "这会儿接不上，我先把你刚才那句留在这里。等会儿再试试。")
            stored = "\n\n".join(t for t in (safety_message, answer) if t)
            self.store.add_message(conv_id, "assistant", stored,
                                   {"provider": provider, "pages": ctx.pages, "safety": check.level,
                                    "safety_message": safety_message,
                                    "events": [e for e in ctx.events if e["type"] in NOTE_EVENTS]})
            return Reply(answer, conv_id, check.level, safety_message, ctx.pages, ctx.events, provider, error)
