"""全部用 mock 模型跑，不联网、不花钱。"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile

os.environ["ANSWERLIFE_HOME"] = tempfile.mkdtemp(prefix="answerlife-test-")
os.environ["AI_PROVIDER"] = "mock"
os.environ["CHECKIN_PUSH"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from answerlife import book, commands, safety  # noqa: E402
from answerlife.agent import Agent  # noqa: E402
from answerlife.channels import Bot, new_pair_code, owner, split_text  # noqa: E402
from answerlife.settings import SKILL_DIR, get_settings  # noqa: E402
from answerlife.store import Store  # noqa: E402
from answerlife.tools import ToolContext  # noqa: E402


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


# ── 安全层 ──
@pytest.mark.parametrize("text,level", [
    ("我真的不想活了", "crisis"), ("已经攒了一瓶安眠药", "crisis"), ("I want to die", "crisis"),
    ("他昨晚又打我了", "danger"), ("活着好累，撑不下去", "concern"),
    ("今天加班累死了", "none"), ("笑死我了哈哈", "none"), ("工作和感情都卡住了", "none"),
])
def test_safety_levels(text, level):
    assert safety.assess(text).level == level


def test_crisis_reply_sent_and_tools_disabled(store):
    r = Agent(store).respond(None, "我不想活了", "cli")
    assert r.safety == "crisis"
    assert "12356" in r.safety_message
    assert "安全" in r.text            # mock 在安全模式下的回复
    assert r.pages == []


def test_crisis_message_survives_model_outage(store, monkeypatch):
    from answerlife import llm

    def boom(*a, **k):
        raise llm.LLMError("network down")
    monkeypatch.setattr(llm, "run", boom)
    r = Agent(store).respond(None, "我想自杀", "web")
    assert "12356" in r.safety_message and r.error


# ── skill 接入 ──
def test_skill_prompt_and_quotes():
    assert "答案之书" in book.skill_text() and "formula.md" in book.skill_text()
    quotes = book.search_quotes("关系与冲突")
    assert quotes and all("关系与冲突" in q["theme"] for q in quotes)
    blocked = [q for q in book.search_quotes(query="apology-30e")]
    assert blocked and not blocked[0]["usable"]


def test_page_rendered_and_recorded_with_consent(store):
    store.set_consent(True)
    r = Agent(store).respond(None, "测试出页", "web")
    assert r.pages, r.text
    page = store.pages()[0]
    assert page["record_id"].startswith("AB-")
    assert (get_settings().pages_dir / page["file"]).exists()
    rv = book.review("2000-01-01", "2999-12-31")
    assert rv["count"] >= 1


def test_page_not_recorded_without_consent(store):
    ctx = ToolContext(store, store.new_conversation("cli"))
    page = json.loads((SKILL_DIR / "examples" / "relationship.json").read_text(encoding="utf-8"))
    out = json.loads(ctx.run("create_answer_page", {"page": page}))
    assert out["ok"] and out["recorded"] is False


def test_invalid_page_returns_error_to_model(store):
    ctx = ToolContext(store, "c1")
    out = json.loads(ctx.run("create_answer_page", {"page": {"title": "x", "original": "伪造原文"}}))
    assert "error" in out


def test_memory_requires_consent(store):
    ctx = ToolContext(store, "c1")
    assert "error" in json.loads(ctx.run("remember", {"kind": "person", "content": "妹妹叫小雨"}))
    ctx.run("set_memory_consent", {"granted": True})
    assert json.loads(ctx.run("remember", {"kind": "person", "content": "妹妹叫小雨"}))["ok"]
    assert store.memories()[0]["content"] == "妹妹叫小雨"


def test_mood_tools_and_commands(store):
    assert "7 分" in commands.handle(store, "/mood 7 有点累")
    ctx = ToolContext(store, "c1")
    ctx.run("log_mood", {"score": 3, "words": "低落"})
    summary = json.loads(ctx.run("mood_summary", {"days": 7}))
    assert summary["count"] == 2 and summary["average"] == 5.0
    assert "平均" in commands.handle(store, "/moods")
    assert commands.handle(store, "随便聊聊") is None
    assert commands.handle(store, "/new") == "__NEW__"


# ── IM 渠道 ──
class FakeAPI:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    async def send(self, chat_id, text):
        self.sent.append((chat_id, text))


def test_bot_pairing_and_stranger_ignored(store):
    api = FakeAPI()
    bot = Bot(api, "telegram", store, Agent(store))
    asyncio.run(bot.message("111", "你好"))
    assert "配对" in api.sent[-1][1]
    code = new_pair_code(store, "telegram")
    asyncio.run(bot.message("111", code))
    assert owner(store, "telegram") == "111"
    asyncio.run(bot.message("111", "最近总是失眠"))
    assert "mock" in api.sent[-1][1]
    n = len(api.sent)
    asyncio.run(bot.message("999", "我是陌生人"))
    assert len(api.sent) == n            # 有主人后，陌生人不回应


def test_pair_code_locks_after_wrong_tries(store):
    api = FakeAPI()
    bot = Bot(api, "feishu", store, Agent(store))
    code = new_pair_code(store, "feishu")
    for _ in range(5):
        asyncio.run(bot.message("x", "000000" if code != "000000" else "111111"))
    asyncio.run(bot.message("x", code))
    assert owner(store, "feishu") is None


def test_split_text():
    chunks = split_text("a" * 9000 + "\n" + "b" * 10, 3800)
    assert all(len(c) <= 3800 for c in chunks) and "".join(chunks).count("a") == 9000


def test_telegram_and_feishu_parsers():
    from types import SimpleNamespace

    from answerlife.channels import dingtalk, feishu, telegram
    assert telegram.parse({"message": {"chat": {"id": 5, "type": "private"}, "text": "hi"}}) == ("5", "hi")
    assert telegram.parse({"message": {"chat": {"id": 5, "type": "group"}, "text": "hi"}}) is None
    msg = SimpleNamespace(message_type="text", chat_type="p2p", content='{"text":"在吗"}', chat_id="oc_1", message_id="m1")
    assert feishu.parse_event(SimpleNamespace(event=SimpleNamespace(message=msg))) == ("oc_1", "在吗", "m1")
    assert dingtalk.parse_event({"conversationType": "1", "msgtype": "text", "senderStaffId": "u1",
                                 "text": {"content": " 在 "}}) == ("u1", "在")


def test_routines_push(store):
    import datetime as dt

    from answerlife import routines
    store.add_page({"id": "p-old", "date": "2000-01-01", "title": "旧的一页", "action": "问三个人", "file": "x.html"})
    store.add_letter("2000-01-01", "2000-02-01", "给未来", "你好，未来的我")
    api = FakeAPI()
    bots = {"telegram": Bot(api, "telegram", store, Agent(store))}
    store.set("channel:telegram:owner", {"chat_id": "42"})
    routines.update(store, {"evening_on": True, "evening_time": "21:30"})
    early = dt.datetime(2026, 11, 5, 20, 0)
    assert sorted(asyncio.run(routines.tick(store, bots, early))) == ["checkin", "letter"]
    assert "你好，未来的我" in api.sent[0][1] and "问三个人" in api.sent[1][1]
    late = dt.datetime(2026, 11, 5, 21, 40)
    assert asyncio.run(routines.tick(store, bots, late)) == ["evening"]
    assert asyncio.run(routines.tick(store, bots, late)) == []      # 每样只发一次


# ── 网页接口 ──
def test_web_api():
    from answerlife.server import app

    with TestClient(app) as c:
        assert "/assets/bird-icons/lovebird.png" in c.get("/").text
        assert c.get("/assets/bird-icons/lovebird.png").headers["content-type"] == "image/png"
        palette = c.get("/api/today").json()["palette"]
        assert len({mood["bird"] for mood in palette}) == 8
        for mood in palette:
            assert c.get(f'/assets/bird-icons/{mood["bird"]}.png').status_code == 200
        r = c.post("/api/chat", json={"text": "最近和朋友吵架了"}).json()
        assert r["conversation_id"] and "mock" in r["reply"]
        conv = c.get(f"/api/conversations/{r['conversation_id']}").json()
        assert len(conv["messages"]) == 2
        assert c.post("/api/chat", json={"text": "/mood 6 还行"}).json()["command"]
        assert c.get("/api/moods").json()
        assert c.post("/api/channels/telegram/pair").json()["code"].isdigit()
        assert c.get("/api/status").json()["provider"] == "mock"
        p = c.post("/api/chat", json={"text": "测试出页"}).json()
        url = p["pages"][0]["url"].split("8020")[1]
        assert "答案之书" in c.get(url).text


def test_tool_loop_forces_reply_when_steps_run_out(store, monkeypatch):
    """模型一直调工具不说话：最后一步不给工具，必须回文字；还是空的话，用出好的页兜底。"""
    from answerlife import llm

    class Looping:
        name, model = "loop", "loop"

        def run(self, blocks, history, tools, execute):
            return llm.Result(llm.EMPTY, self.name, self.model)

    monkeypatch.setattr(llm, "build", lambda kind, s: Looping())
    agent = Agent(store)
    r = agent.respond(None, "随便聊聊", "web")
    assert r.text == llm.EMPTY                         # 没有出页时如实显示
    ctx_page = {"title": "一页", "url": "http://x/pages/a.html", "criterion": "判据"}
    import answerlife.agent as agent_mod
    orig = agent_mod.ToolContext

    class Ctx(orig):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.pages.append(ctx_page)
    monkeypatch.setattr(agent_mod, "ToolContext", Ctx)
    r = agent.respond(None, "帮我翻一页", "web")
    assert ctx_page["url"] in r.text and ctx_page["criterion"] not in r.text


def test_openai_loop_last_step_disables_tools(monkeypatch):
    """OpenAI 兼容实现：工具步数用满后，最后一次请求带 tool_choice=none。"""
    from types import SimpleNamespace

    from answerlife import llm
    from answerlife.settings import get_settings

    seen = []

    def fake_create(**kw):
        seen.append(kw.get("tool_choice"))
        if kw.get("tool_choice") == "none":
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="好，说完了。", tool_calls=None))])
        tc = SimpleNamespace(id=f"t{len(seen)}", function=SimpleNamespace(name="log_mood", arguments='{"score":5}'),
                             model_dump=lambda: {"id": "t", "type": "function", "function": {"name": "log_mood", "arguments": "{}"}})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[tc]))])

    s = get_settings()
    impl = llm.OpenAICompatLLM.__new__(llm.OpenAICompatLLM)
    impl.s, impl.name, impl.model = s, "deepseek", "deepseek-chat"
    impl.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))
    tools = [{"name": "log_mood", "description": "x", "input_schema": {"type": "object", "properties": {}}}]
    r = impl.run([("sys", True)], [{"role": "user", "content": "hi"}], tools, lambda n, a: "{}")
    assert r.text == "好，说完了。" and seen[-1] == "none" and len(seen) == llm.MAX_STEPS + 1
