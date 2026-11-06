"""Agent 的工具。分两层：

- 核心工具（任何时候都在）：读 skill、长期记忆、情绪打卡、日记。
- skill 工具（来自 skill_tools/，对应的 skill 启用时才出现）：答案之书出页、呼吸练习、未来信……

工具定义用中性格式（name / description / input_schema），由 llm.py 转成各家接口的格式。
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field

from answerlife import skills as skill_registry
from answerlife.settings import today
from answerlife.skill_tools import MODULES
from answerlife.store import MEMORY_KINDS, Store

JOURNAL_KINDS = ("thought", "good-things", "note", "reflection")

CORE_SPECS: list[dict] = [
    {"name": "use_skill",
     "description": "读取一个 skill 的完整说明并在本段对话里激活它。在按某个 skill 的方法做事之前先调用；已激活的不必重复调用。",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "read_skill_file",
     "description": "读取已激活 skill 目录里的参考文件（相对路径，见 use_skill 返回的 files）。",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "path": {"type": "string"}},
                      "required": ["name", "path"]}},
    {"name": "remember",
     "description": "保存一条关于用户的长期记忆（一句话）。需要用户已同意。只存用户亲口说过的事实，不存推断和敏感身份信息。",
     "input_schema": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": list(MEMORY_KINDS)}, "content": {"type": "string"}},
         "required": ["kind", "content"]}},
    {"name": "forget",
     "description": "删除一条长期记忆（用编号）。",
     "input_schema": {"type": "object", "properties": {"memory_id": {"type": "integer"}}, "required": ["memory_id"]}},
    {"name": "set_memory_consent",
     "description": "记录用户是否同意在本机保存长期记忆、日记与实验记录。只在用户明确表态后调用。",
     "input_schema": {"type": "object", "properties": {"granted": {"type": "boolean"}}, "required": ["granted"]}},
    {"name": "log_mood",
     "description": ("情绪打卡：记下此刻的心情分数（1 很糟 – 10 很好）和用户自己用的几个词。"
                    "words 以一个情绪名开头（开心、期待、平静、疲惫、焦虑、委屈、生气、难过 之一，选最贴近用户原话的），"
                    "后面接用户自己的词，例如“焦虑 明天要答辩”。"),
     "input_schema": {"type": "object", "properties": {
         "score": {"type": "integer", "minimum": 1, "maximum": 10},
         "words": {"type": "string"}, "note": {"type": "string"}}, "required": ["score"]}},
    {"name": "mood_summary",
     "description": "最近 N 天的情绪打卡记录与均值。",
     "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 92}},
                      "required": []}},
    {"name": "save_journal",
     "description": ("把用户确认过的一段内容存进日记：thought=想法记录，good-things=三件小事，reflection=复盘，note=其他。"
                     "需要用户已同意保存。内容用用户自己的话。"),
     "input_schema": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": list(JOURNAL_KINDS)},
         "title": {"type": "string"}, "content": {"type": "string"}}, "required": ["kind", "content"]}},
]

SKILL_TOOLS = {spec["name"]: (m.SKILL, getattr(m, spec["name"]), spec) for m in MODULES for spec in m.SPECS}


def specs_for(enabled_skills: set[str], urgent: bool = False) -> list[dict]:
    """本轮交给模型的工具。安全模式下只留记忆类工具：不出页、不布置任务。"""
    if urgent:
        return [s for s in CORE_SPECS if s["name"] in ("remember", "set_memory_consent")]
    return CORE_SPECS + [spec for _, (skill, _, spec) in SKILL_TOOLS.items() if skill in enabled_skills]


@dataclass
class ToolContext:
    store: Store
    conv_id: str
    events: list[dict] = field(default_factory=list)
    pages: list[dict] = field(default_factory=list)

    def emit(self, kind: str, **data) -> None:
        self.events.append({"type": kind, **data})

    def run(self, name: str, args: dict) -> str:
        """执行一个工具，返回给模型的文本。出错时返回错误说明，交给模型自己修正。"""
        self.emit("tool", name=name)
        try:
            if name in SKILL_TOOLS:
                skill, fn, _ = SKILL_TOOLS[name]
                if skill not in skill_registry.enabled(self.store):
                    raise ValueError(f"skill {skill} 已停用")
                result = fn(self, **(args or {}))
            elif hasattr(self, f"_t_{name}"):
                result = getattr(self, f"_t_{name}")(**(args or {}))
            else:
                result = {"error": f"没有这个工具：{name}"}
        except (ValueError, KeyError, TypeError, OSError) as e:
            result = {"error": str(e)}
        return json.dumps(result, ensure_ascii=False, default=str)

    # ── skill ──
    def _t_use_skill(self, name: str) -> dict:
        found = skill_registry.enabled(self.store).get(name)
        if not found:
            return {"error": f"没有启用的 skill：{name}"}
        skill_registry.activate(self.store, self.conv_id, name)
        self.emit("skill", name=name, title=found.title or name)
        return {"name": name, "instructions": found.body, "files": found.files(),
                "note": "已激活，之后几轮对话里这份说明会一直在系统提示词中。"}

    def _t_read_skill_file(self, name: str, path: str) -> dict:
        found = skill_registry.enabled(self.store).get(name)
        if not found:
            return {"error": f"没有启用的 skill：{name}"}
        return {"path": path, "content": found.read(path)}

    # ── 记忆 ──
    def _need_consent(self) -> dict | None:
        consent = self.store.consent()
        if consent is True:
            return None
        return {"error": "还没有取得用户同意，先问一句再保存。" if consent is None else "用户拒绝了保存长期记录，不要再存。"}

    def _t_remember(self, kind: str, content: str) -> dict:
        if (err := self._need_consent()):
            return err
        mid = self.store.remember(kind, content, self.conv_id)
        self.emit("memory", id=mid, content=content)
        return {"ok": True, "id": mid}

    def _t_forget(self, memory_id: int) -> dict:
        return {"ok": self.store.forget(int(memory_id))}

    def _t_set_memory_consent(self, granted: bool) -> dict:
        self.store.set_consent(bool(granted))
        self.emit("consent", granted=bool(granted))
        return {"ok": True, "granted": bool(granted)}

    # ── 情绪与日记 ──
    def _t_log_mood(self, score: int, words: str = "", note: str = "") -> dict:
        mid = self.store.log_mood(today(), int(score), words, note, self.conv_id)
        self.emit("mood", score=int(score), words=words)
        return {"ok": True, "id": mid, "date": today()}

    def _t_mood_summary(self, days: int = 14) -> dict:
        end = dt.date.fromisoformat(today())
        start = end - dt.timedelta(days=int(days) - 1)
        rows = self.store.moods(start.isoformat(), end.isoformat())
        avg = round(sum(r["score"] for r in rows) / len(rows), 1) if rows else None
        return {"start": start.isoformat(), "end": end.isoformat(), "count": len(rows), "average": avg, "entries": rows,
                "note": "只反映已打卡的日子，不代表全部情绪。"}

    def _t_save_journal(self, kind: str, content: str, title: str = "") -> dict:
        if (err := self._need_consent()):
            return err
        if kind not in JOURNAL_KINDS:
            kind = "note"
        jid = self.store.add_journal(today(), kind, title, content, self.conv_id)
        self.emit("journal", id=jid, journal_kind=kind, title=title)
        return {"ok": True, "id": jid}
