from types import SimpleNamespace

from answerlife import reflections
from answerlife.store import Store


def test_week_and_month_use_separate_records_and_verified_book_cards(monkeypatch):
    monkeypatch.setattr(reflections, "today", lambda: "2026-11-06")
    store = Store(":memory:")
    store.add_journal("2026-11-01", "note", "补觉", "加班以后想休息一天")
    store.add_journal("2026-11-05", "note", "面试", "两次面试都在问我怎么和客户沟通")
    store.add_journal("2026-11-07", "note", "明天", "这条未来记录不该进来")
    store.log_mood("2026-11-06", 3, "焦虑")

    week = reflections.report(store, "week")
    month = reflections.report(store, "month")
    assert (week["start"], month["start"], week["end"]) == ("2026-11-02", "2026-11-01", "2026-11-06")
    assert week["quote"]["id"] == "lunyu-2-12"
    assert week["quote"]["text"] == "君子不器。"
    assert week["quote"]["url"].startswith("https://")
    letter = " ".join(week["paragraphs"])
    assert "两次面试" in letter
    assert "加班" not in letter and "未来记录" not in letter
    assert week["mode"] == "local"


def test_model_rewrite_is_explicit_and_cannot_replace_the_book_card(monkeypatch):
    monkeypatch.setattr(reflections, "today", lambda: "2026-11-06")
    monkeypatch.setattr(reflections, "get_settings", lambda: SimpleNamespace(provider="openai", timezone="Asia/Shanghai"))
    store = Store(":memory:")
    store.log_mood("2026-11-06", 4, "疲惫")
    calls = []

    def generate(*args):
        calls.append(args)
        return SimpleNamespace(refused=False, text='{"paragraphs":["这一周有一次疲惫的打卡，可以留一点时间歇一歇。"],"quote":"编的"}')

    monkeypatch.setattr(reflections.llm, "run", generate)
    local = reflections.report(store, "week")
    assert not calls
    rewritten = reflections.report(store, "week", use_model=True)
    assert len(calls) == 1 and rewritten["mode"] == "model"
    assert rewritten["quote"] == local["quote"]
    assert rewritten["paragraphs"] != local["paragraphs"]
