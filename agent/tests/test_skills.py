"""skill 生态、陪伴类工具、网页新接口。mock 模型，不联网。"""

from __future__ import annotations

import json
import os
import tempfile

os.environ.setdefault("ANSWERLIFE_HOME", tempfile.mkdtemp(prefix="answerlife-test-"))
os.environ["AI_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from answerlife import skills as registry  # noqa: E402
from answerlife import soul  # noqa: E402
from answerlife.agent import Agent  # noqa: E402
from answerlife.store import Store  # noqa: E402
from answerlife.tools import CORE_SPECS, ToolContext, specs_for  # noqa: E402

BUILTIN = {"mood-weather", "calm-breath", "answer-book", "hard-talk", "thought-record", "good-things", "future-letter"}


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_builtin_skills_discovered_with_ui_meta():
    found = registry.discover()
    assert BUILTIN <= set(found)
    for name in BUILTIN:
        s = found[name]
        assert s.title and s.starter and s.color.startswith("#"), name
        assert s.body and not s.body.startswith("---"), name
    assert list(found)[0] == "mood-weather"          # 按 order 排序


def test_index_in_prompt_but_not_full_body(store):
    text = soul.static_prompt(store)
    assert "hard-talk" in text and "future-letter" in text
    assert "观察-感受-需要-请求" not in text.split("可用 skill")[0]
    assert "# 难开口的话" not in text                  # 全文只在激活后出现


def test_use_skill_activates_and_body_enters_prompt(store):
    cid = store.new_conversation("cli")
    ctx = ToolContext(store, cid)
    out = json.loads(ctx.run("use_skill", {"name": "hard-talk"}))
    assert "非暴力沟通" in out["instructions"]
    assert registry.active(store, cid) == ["hard-talk"]
    assert "# 难开口的话" in soul.active_prompt(store, cid)
    files = json.loads(ctx.run("use_skill", {"name": "answer-book"}))["files"]
    assert "references/formula.md" in files
    assert "一页的写法" in json.loads(ctx.run("read_skill_file", {"name": "answer-book", "path": "references/formula.md"}))["content"]
    assert "error" in json.loads(ctx.run("read_skill_file", {"name": "answer-book", "path": "../../settings.py"}))


def test_disabled_skill_hides_its_tools(store):
    names = {s["name"] for s in specs_for(set(registry.enabled(store)))}
    assert {"create_answer_page", "start_breathing", "seal_letter"} <= names
    registry.set_enabled(store, "answer-book", False)
    names = {s["name"] for s in specs_for(set(registry.enabled(store)))}
    assert "create_answer_page" not in names and "start_breathing" in names
    ctx = ToolContext(store, "c")
    assert "停用" in json.loads(ctx.run("search_quotes", {}))["error"]
    assert "error" in json.loads(ctx.run("use_skill", {"name": "answer-book"}))


def test_urgent_mode_has_no_task_tools():
    names = {s["name"] for s in specs_for(BUILTIN, urgent=True)}
    assert names <= {s["name"] for s in CORE_SPECS} and "start_breathing" not in names


def test_install_third_party_skill_is_text_only(tmp_path, store):
    src = tmp_path / "pkg" / "walk-outside"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: walk-outside\ndescription: 出门走走：陪用户安排一次十分钟的散步。\n---\n\n# 出门走走\n\n走十分钟。\n",
                                  encoding="utf-8")
    (src / "tools.py").write_text("raise SystemExit('should never run')\n", encoding="utf-8")
    s = registry.install(str(tmp_path / "pkg"))
    assert s.name == "walk-outside" and not s.builtin
    assert "walk-outside" in registry.enabled(store)
    assert "walk-outside" not in {spec["name"] for spec in specs_for({"walk-outside"})}
    assert registry.uninstall("walk-outside") and "walk-outside" not in registry.discover()


def test_install_rejects_bad_frontmatter(tmp_path):
    (tmp_path / "SKILL.md").write_text("# 没有 frontmatter\n", encoding="utf-8")
    with pytest.raises(ValueError):
        registry.install(str(tmp_path))


def test_breathing_and_letter_tools(store):
    ctx = ToolContext(store, "c")
    out = json.loads(ctx.run("start_breathing", {"pattern": "box"}))
    assert out["ok"] and any(e["type"] == "breathing" and e["rounds"] == 4 for e in ctx.events)
    assert "error" in json.loads(ctx.run("seal_letter", {"deliver_on": "2000-01-01", "content": "x"}))
    assert "error" in json.loads(ctx.run("seal_letter", {"deliver_on": "2099-01-01", "content": "x"}))
    assert json.loads(ctx.run("seal_letter", {"deliver_on": "2027-01-01", "content": "你好", "title": "新年"}))["ok"]
    listed = json.loads(ctx.run("list_letters", {}))
    assert listed["sealed"][0]["title"] == "新年" and "content" not in listed["sealed"][0]   # 没到日子看不到内容


def test_journal_requires_consent(store):
    ctx = ToolContext(store, "c")
    assert "error" in json.loads(ctx.run("save_journal", {"kind": "thought", "content": "我很失败"}))
    store.set_consent(True)
    assert json.loads(ctx.run("save_journal", {"kind": "good-things", "content": "吃到了好吃的面"}))["ok"]
    assert store.journal()[0]["kind"] == "good-things"


def test_skill_preactivated_from_ui(store):
    r = Agent(store).respond(None, "带我呼吸一下", "web", skill="calm-breath")
    assert registry.active(store, r.conv_id) == ["calm-breath"]
    assert any(e["type"] == "breathing" for e in r.events)
    note_types = {e["type"] for e in store.messages(r.conv_id)[-1]["meta"]["events"]}
    assert "skill" in note_types


def test_skill_command_in_im(store):
    import asyncio

    from answerlife.channels import Bot

    class API:
        sent: list = []

        async def send(self, chat_id, text):
            self.sent.append(text)

    store.set("channel:telegram:owner", {"chat_id": "1"})
    api = API()
    asyncio.run(Bot(api, "telegram", store, Agent(store)).message("1", "/skills"))
    assert "难开口的话" in api.sent[-1]
    asyncio.run(Bot(api, "telegram", store, Agent(store)).message("1", "/skill good-things"))
    conv = store.get("channel:telegram:conv")
    assert registry.active(store, conv) == ["good-things"]


def test_web_today_skills_settings():
    from answerlife.server import app

    with TestClient(app) as c:
        assert c.post("/api/mood", json={"emotion": "难过"}).json()["score"] == 2
        today = c.get("/api/today").json()
        assert today["today_moods"] and len(today["skills"]) >= 7
        skills = c.get("/api/skills").json()
        assert any(s["name"] == "answer-book" and s["has_tools"] for s in skills)
        assert c.post("/api/skills/hard-talk/off").json()["ok"]
        assert not next(s for s in c.get("/api/skills").json() if s["name"] == "hard-talk")["enabled"]
        c.post("/api/skills/hard-talk/on")
        r = c.post("/api/chat", json={"text": "/skill calm-breath"}).json()
        assert "calm-breath" in r["skills"]
        st = c.put("/api/settings", json={"routines": {"evening_on": True, "evening_time": "22:00"}}).json()
        assert st["routines"]["evening_on"] and st["routines"]["evening_time"] == "22:00"
        assert c.put("/api/settings", json={"routines": {"evening_time": "25:99"}}).status_code == 400
        assert "我的答案之书" in c.get("/api/settings").json()["soul"]
        c.put("/api/settings", json={"soul": "# SOUL\n\n你叫小羽。"})
        assert "小羽" in soul.soul()


def test_emotion_map_counts_and_fallback(store):
    from answerlife import emotions
    for name in ("焦虑", "焦虑", "开心"):
        store.log_mood("2026-11-05", emotions.PALETTE[name][0], name + " 有点事")
    store.log_mood("2026-11-04", 7, "IM 里打的卡")          # 没有情绪名：按分数归到“平静”
    m = emotions.emotion_map(store, "2026-11-05", 7)
    assert m["total"] == 4 and m["bubbles"][0] == {"name": "焦虑", "count": 2, "color": "#F2A65A", "score": 3}
    assert {b["name"] for b in m["bubbles"]} == {"焦虑", "开心", "平静"}
    assert [d["date"] for d in m["days"]] == ["2026-11-04", "2026-11-05"]
