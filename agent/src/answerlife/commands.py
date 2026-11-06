"""不调用模型的命令：终端和 IM 共用。返回 None 表示这不是命令，交给 Agent。"""

from __future__ import annotations

import re

from answerlife.settings import get_settings, today
from answerlife.store import Store

HELP = (
    "直接说话就好。想理清一件事可以说“帮我翻一页”，只想说说也可以。\n\n"
    "不调用模型的命令：\n"
    "/mood 7 有点累 — 情绪打卡（1–10 分加几个词）\n"
    "/moods — 最近 14 天的打卡\n"
    "/pages — 最近的答案页\n"
    "/memory — 我记下的关于你的事；/forget 编号 删一条；/forget all 全部清空\n"
    "/consent on|off — 同意或拒绝在本机保存记忆与实验记录\n"
    "/skills — 我会的几件事；/skill 名字 — 直接开始其中一件\n"
    "/new — 开始一段新对话\n"
    "/status — 当前状态"
)


def handle(store: Store, text: str) -> str | None:
    t = text.strip()
    alias = {"帮助": "/help", "技能": "/skills", "记忆": "/memory", "答案页": "/pages", "新对话": "/new", "状态": "/status", "心情": "/moods"}
    t = alias.get(t, t)
    if not t.startswith("/"):
        return None
    cmd, _, arg = t.partition(" ")
    arg = arg.strip()
    if cmd in ("/help", "/start"):
        return HELP
    if cmd == "/mood":
        m = re.match(r"(\d{1,2})\s*(.*)", arg)
        if not m or not 1 <= int(m[1]) <= 10:
            return "用法：/mood 7 有点累（1 很糟 – 10 很好）"
        store.log_mood(today(), int(m[1]), m[2])
        return f"记下了：{today()} {m[1]} 分" + (f"，{m[2]}" if m[2] else "") + "。想说说的话，我在。"
    if cmd == "/moods":
        import datetime as dt
        end = dt.date.fromisoformat(today())
        rows = store.moods((end - dt.timedelta(days=13)).isoformat(), end.isoformat())
        if not rows:
            return "最近 14 天还没有打卡。可以发 /mood 7 有点累 试试。"
        avg = sum(r["score"] for r in rows) / len(rows)
        lines = [f"{r['date']}  {'●' * r['score']}{'○' * (10 - r['score'])}  {r['words']}" for r in rows]
        return "\n".join(lines) + f"\n\n{len(rows)} 次打卡，平均 {avg:.1f} 分。只反映打过卡的日子。"
    if cmd == "/pages":
        rows = store.pages(10)
        if not rows:
            return "还没有答案页。说一件最近绕不过去的事，我们一起翻一页。"
        base = get_settings().base_url
        return "\n\n".join(f"{p['date']}《{p['title'].replace(chr(10), '')}》\n实验：{p['action'][:60]}\n{base}/pages/{p['file']}"
                           for p in rows)
    if cmd == "/memory":
        consent = {None: "还没问过你", True: "你已同意", False: "你已拒绝"}[store.consent()]
        rows = store.memories()
        if not rows:
            return f"我还没有记下任何关于你的事（保存记忆：{consent}）。"
        return f"保存记忆：{consent}\n" + "\n".join(f"#{m['id']} [{m['kind']}] {m['content']}" for m in rows)
    if cmd == "/forget":
        if arg == "all":
            store.forget_all()
            return "已清空全部长期记忆和情绪打卡。对话记录可以在网页里逐个删除。"
        if arg.lstrip("#").isdigit():
            return "删掉了。" if store.forget(int(arg.lstrip("#"))) else "没有这个编号。"
        return "用法：/forget 3 或 /forget all"
    if cmd == "/consent":
        if arg in ("on", "off"):
            store.set_consent(arg == "on")
            return "好，之后会在本机记下关键事实和实验记录。" if arg == "on" else "好，之后不再保存任何长期记录。"
        return "用法：/consent on 或 /consent off"
    if cmd == "/status":
        s = get_settings()
        model = {"anthropic": s.anthropic_model, "deepseek": s.deepseek_model}.get(s.provider, s.openai_model or s.provider)
        return (f"模型：{s.provider} · {model}" + (f"（备用 {s.fallback}）" if s.fallback else "")
                + f"\n数据目录：{s.home}\n长期记忆：{len(store.memories())} 条 · 答案页：{len(store.pages(1000))} 页")
    if cmd == "/new":
        return "__NEW__"
    if cmd == "/skills":
        from answerlife import skills as registry
        found = registry.enabled(store)
        return "我会的几件事（发 /skill 名字 开始）：\n\n" + "\n".join(
            f"{s.title or s.name}（{s.name}）— {s.tagline or s.description[:30]}" for s in found.values())
    if cmd == "/skill":
        from answerlife import skills as registry
        found = registry.enabled(store).get(arg)
        if not found:
            return "没有这个 skill。发 /skills 看看有哪些。"
        return "__SKILL__:" + arg
    return f"不认识的命令：{cmd}。发 /help 看看能做什么。"
