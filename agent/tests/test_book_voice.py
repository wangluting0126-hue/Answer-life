"""The same authored voice is used for chat and rendered pages."""

import json

from answerlife import book, llm
from answerlife.agent import Agent
from answerlife.settings import SKILL_DIR
from answerlife.store import Store
from answerlife.tools import ToolContext


CANNED = "这份对照只能帮助选择下一步，不能保证面试。"


def test_generated_report_is_polished_without_rewriting_user_words(tmp_path):
    store = Store(tmp_path / "test.db")
    page = json.loads((SKILL_DIR / "examples" / "job-search.json").read_text(encoding="utf-8"))
    page["quote"] = CANNED
    page["criterion"] = CANNED
    ctx = ToolContext(store, store.new_conversation("web"))
    result = json.loads(ctx.run("create_answer_page", {"page": page}))
    assert result["ok"]
    assert ctx.pages[0]["criterion"] == "先看看这份对照里，哪一处值得改。"
    from pathlib import Path

    snapshot = json.loads(Path(ctx.pages[0]["path"]).with_suffix(".json").read_text(encoding="utf-8"))["pages"][0]
    assert snapshot["quote"] == CANNED
    assert snapshot["_source"]["original"] == book.ab().bank()[page["quote_id"]]["original"]
    assert snapshot["assessment"] == page["assessment"]


def test_chat_drops_canned_opening_and_keeps_concrete_uncertainty(tmp_path, monkeypatch):
    def response(*args):
        return llm.Result("我理解你的感受。" + CANNED + "没看过那份简历，先不猜为什么没回音。", "mock", "mock")

    monkeypatch.setattr(llm, "run", response)
    reply = Agent(Store(tmp_path / "test.db")).respond(None, "投出去没回音", "web")
    assert reply.text == "先看看这份对照里，哪一处值得改。没看过那份简历，先不猜为什么没回音。"
