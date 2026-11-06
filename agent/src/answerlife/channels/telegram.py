"""Telegram：长轮询 getUpdates，不需要公网地址。只处理私聊文字。"""

from __future__ import annotations

import asyncio
import logging

import httpx

from answerlife.channels import Bot, split_text

log = logging.getLogger("answerlife.channel.telegram")
CHUNK = 3800   # 单条上限 4096


class Telegram:
    def __init__(self, token: str, http: httpx.AsyncClient | None = None) -> None:
        self.base = f"https://api.telegram.org/bot{token}"
        self.http = http or httpx.AsyncClient(timeout=40.0)
        self.error = ""

    async def send(self, chat_id: str, text: str) -> None:
        for chunk in split_text(text, CHUNK) or ["（空）"]:
            resp = await self.http.post(f"{self.base}/sendMessage", json={"chat_id": chat_id, "text": chunk})
            if resp.status_code >= 400:
                log.warning("Telegram 发送失败：%s", resp.text[:200])

    async def updates(self, offset: int) -> list[dict]:
        resp = await self.http.get(f"{self.base}/getUpdates", params={"offset": offset, "timeout": 30,
                                                                     "allowed_updates": '["message"]'})
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description") or f"HTTP {resp.status_code}")
        return data.get("result", [])


def parse(update: dict) -> tuple[str, str] | None:
    msg = update.get("message") or {}
    chat = msg.get("chat") or {}
    if chat.get("type") != "private" or not msg.get("text"):
        return None
    return str(chat["id"]), msg["text"]


async def run(bot: Bot) -> None:
    api: Telegram = bot.api
    offset = int(bot.store.get("channel:telegram:offset") or 0)
    tasks: set[asyncio.Task] = set()
    while True:
        try:
            for update in await api.updates(offset):
                offset = update["update_id"] + 1
                bot.store.set("channel:telegram:offset", offset)
                parsed = parse(update)
                if parsed:
                    task = asyncio.create_task(bot.message(*parsed))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
            api.error = ""
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001  网络中断、token 不对：记下来，过一会儿再试
            api.error = f"Telegram 连接出错：{e}"
            log.warning("%s", api.error)
            await asyncio.sleep(10)
