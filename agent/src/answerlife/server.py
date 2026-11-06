"""单进程网关：网页 + 接口 + IM 渠道 + 陪伴节奏，全部跟着一个进程跑。

结构参考 OpenClaw 的 Gateway：渠道只管收发，统一交给同一个 Agent；本项目把它做成一个 FastAPI 进程（同 wealthpilot）。
默认只监听 127.0.0.1：情感对话是最私密的数据，不要把端口直接暴露到公网。
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
from socket import socket
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from answerlife import __version__, commands, emotions, reflections, routines, soul
from answerlife import skills as registry
from answerlife.agent import Agent
from answerlife.channels import CHANNELS, Bot, new_pair_code, owner
from answerlife.settings import PACKAGE, get_settings, today
from answerlife.store import Store

log = logging.getLogger("answerlife.server")



class Runtime:
    """进程里共用的一份：存储、Agent、各渠道的机器人。"""

    def __init__(self) -> None:
        s = get_settings()
        self.store = Store(s.db_path)
        self.agent = Agent(self.store)
        self.bots: dict[str, Bot] = {}
        self.tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        s = get_settings()
        loop = asyncio.get_running_loop()
        if s.telegram_bot_token:
            from answerlife.channels import telegram
            bot = Bot(telegram.Telegram(s.telegram_bot_token), "telegram", self.store, self.agent)
            self.bots["telegram"] = bot
            self.tasks.append(asyncio.create_task(telegram.run(bot)))
        if s.feishu_app_id and s.feishu_app_secret:
            from answerlife.channels import feishu
            bot = Bot(feishu.Feishu(s.feishu_app_id, s.feishu_app_secret, s.feishu_api_base), "feishu", self.store, self.agent)
            self.bots["feishu"] = bot
            feishu.Listener(bot, loop).start()
        if s.dingtalk_client_id and s.dingtalk_client_secret:
            from answerlife.channels import dingtalk
            bot = Bot(dingtalk.DingTalk(s.dingtalk_client_id, s.dingtalk_client_secret), "dingtalk", self.store, self.agent)
            self.bots["dingtalk"] = bot
            dingtalk.start(bot, loop)
        self.tasks.append(asyncio.create_task(self.routine_loop()))

    async def routine_loop(self) -> None:
        while True:
            try:
                await routines.tick(self.store, self.bots)
            except Exception as e:  # noqa: BLE001
                log.warning("陪伴节奏出错：%s", e)
            await asyncio.sleep(60)

    def channel_status(self) -> list[dict]:
        out = []
        for key, name in CHANNELS.items():
            bot = self.bots.get(key)
            out.append({"channel": key, "name": name, "configured": bot is not None,
                        "paired": bool(owner(self.store, key)), "error": getattr(bot.api, "error", "") if bot else ""})
        return out


runtime: Runtime | None = None


def rt() -> Runtime:
    global runtime
    if runtime is None:
        runtime = Runtime()
    return runtime


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await rt().start()
    yield
    for task in rt().tasks:
        task.cancel()


app = FastAPI(title="我的答案之书", lifespan=lifespan)
WEB = PACKAGE / "web"


class ChatIn(BaseModel):
    text: str
    conversation_id: str | None = None
    skill: str | None = None


class MoodIn(BaseModel):
    emotion: str
    words: str = ""


class SettingsIn(BaseModel):
    soul: str | None = None
    routines: dict | None = None
    consent: bool | None = None


def _model_label() -> dict:
    s = get_settings()
    model = {"anthropic": s.anthropic_model, "deepseek": s.deepseek_model}.get(s.provider, s.openai_model or s.provider)
    return {"provider": s.provider, "model": model, "fallback": s.fallback}


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# ── 对话 ──
@app.post("/api/chat")
async def chat(body: ChatIn) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "空消息")
    cmd = commands.handle(rt().store, text)
    if cmd and cmd.startswith("__SKILL__:"):
        from answerlife.channels import _starter
        body.skill, body.conversation_id = cmd.split(":", 1)[1], None
        text, cmd = _starter(body.skill), None
    if cmd == "__NEW__":
        return {"conversation_id": None, "reply": "好，我们重新开始。", "command": True, "new": True}
    if cmd is not None:
        return {"conversation_id": body.conversation_id, "reply": cmd, "command": True}
    r = await asyncio.to_thread(rt().agent.respond, body.conversation_id, text, "web", body.skill)
    return {"conversation_id": r.conv_id, "reply": r.text, "safety": r.safety, "safety_message": r.safety_message,
            "pages": r.pages, "events": r.events, "provider": r.provider, "error": r.error,
            "skills": registry.active(rt().store, r.conv_id)}


@app.get("/api/conversations")
def conversations() -> list[dict]:
    return rt().store.conversations()


@app.get("/api/conversations/{cid}")
def conversation(cid: str) -> dict:
    conv = rt().store.conversation(cid)
    if not conv:
        raise HTTPException(404, "没有这段对话")
    return {**conv, "messages": rt().store.messages(cid), "skills": registry.active(rt().store, cid)}


@app.delete("/api/conversations/{cid}")
def delete_conversation(cid: str) -> dict:
    rt().store.delete_conversation(cid)
    rt().store.delete_key(f"conv:{cid}:skills")
    return {"ok": True}


# ── 今天 ──
@app.get("/api/today")
def today_view() -> dict:
    store, d = rt().store, today()
    end = dt.date.fromisoformat(d)
    moods = store.moods((end - dt.timedelta(days=34)).isoformat(), d)
    last = next((m for m in reversed(moods) if m["date"] == d), None)
    return {"date": d, "moods": moods, "today_moods": [m for m in moods if m["date"] == d],
            "palette": emotions.palette(),
            "last_emotion": (emotions.name_of(last["words"]) or emotions.from_score(last["score"])) if last else None,
            "skills": [s.card(True) for s in registry.enabled(store).values()],
            "recent": store.conversations(4), **routines.home_cards(store), **_model_label()}


@app.post("/api/mood")
def mood(body: MoodIn) -> dict:
    if body.emotion not in emotions.PALETTE:
        raise HTTPException(400, "未知情绪")
    score, color, face = emotions.PALETTE[body.emotion]
    date = today()
    rt().store.log_mood(date, score, (body.emotion + " " + body.words).strip())
    return {"ok": True, "emotion": body.emotion, "score": score, "color": color, "face": face, "date": date}


@app.get("/api/emotions")
def emotion_view(days: int = 30) -> dict:
    return {"palette": emotions.palette(), **emotions.emotion_map(rt().store, today(), max(1, min(days, 366)))}


# ── skill ──
@app.get("/api/skills")
def list_skills() -> list[dict]:
    on = set(registry.enabled(rt().store))
    return [s.card(s.name in on) | {"source": "内置" if s.builtin else "已安装", "files": s.files()}
            for s in registry.discover().values()]


@app.post("/api/skills/{name}/{state}")
def toggle_skill(name: str, state: str) -> dict:
    if name not in registry.discover() or state not in ("on", "off"):
        raise HTTPException(404, "没有这个 skill")
    registry.set_enabled(rt().store, name, state == "on")
    return {"ok": True}


# ── 记录 ──
@app.get("/api/journal")
def journal() -> list[dict]:
    return rt().store.journal(100)


@app.delete("/api/journal/{jid}")
def delete_journal(jid: int) -> dict:
    return {"ok": rt().store.delete_journal(jid)}


@app.get("/api/letters")
def letters() -> dict:
    return rt().store.letters(today())


@app.delete("/api/letters/{lid}")
def delete_letter(lid: int) -> dict:
    return {"ok": rt().store.delete_letter(lid)}


@app.get("/api/memories")
def memories() -> dict:
    return {"consent": rt().store.consent(), "memories": rt().store.memories()}


@app.delete("/api/memories/{mid}")
def forget(mid: int) -> dict:
    return {"ok": rt().store.forget(mid)}


@app.get("/api/moods")
def moods(days: int = 30) -> list[dict]:
    end = dt.date.fromisoformat(today())
    return rt().store.moods((end - dt.timedelta(days=days - 1)).isoformat(), end.isoformat())


@app.get("/api/reflections/{period}")
def read_reflection(period: Literal["week", "month"]) -> dict:
    return reflections.report(rt().store, period)


@app.post("/api/reflections/{period}")
def write_reflection(period: Literal["week", "month"]) -> dict:
    return reflections.report(rt().store, period, use_model=True)


@app.get("/api/pages")
def pages() -> list[dict]:
    return rt().store.pages()


# ── 设置 ──
@app.get("/api/settings")
def get_settings_view() -> dict:
    return {"soul": soul.soul(), "routines": routines.config(rt().store), "consent": rt().store.consent(),
            "channels": rt().channel_status(), "home": str(get_settings().home), **_model_label()}


@app.put("/api/settings")
def put_settings(body: SettingsIn) -> dict:
    if body.soul is not None:
        if not body.soul.strip():
            raise HTTPException(400, "人格不能为空")
        soul.save_soul(body.soul)
    if body.routines is not None:
        try:
            routines.update(rt().store, body.routines)
        except ValueError as e:
            raise HTTPException(400, f"时间格式不对：{e}") from e
    if body.consent is not None:
        rt().store.set_consent(body.consent)
    return get_settings_view()


@app.get("/api/status")
def status() -> dict:
    return {**_model_label(), "home": str(get_settings().home), "channels": rt().channel_status(),
            "consent": rt().store.consent(), "app": "answerlife", "version": __version__}


@app.post("/api/channels/{channel}/pair")
def pair(channel: str) -> dict:
    if channel not in CHANNELS:
        raise HTTPException(404, "没有这个渠道")
    return {"code": new_pair_code(rt().store, channel), "expires_in": 600}


app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")
app.mount("/pages", StaticFiles(directory=str(get_settings().pages_dir)), name="pages")


def serve(host: str | None = None, port: int | None = None, log_level: str = "warning",
          *, listener: socket | None = None) -> None:
    import uvicorn

    s = get_settings()
    config = uvicorn.Config(app, host=host or s.host, port=port or s.port, log_level=log_level)
    uvicorn.Server(config).run(sockets=[listener] if listener is not None else None)
