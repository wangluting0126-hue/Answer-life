"""IM 渠道：Telegram（长轮询）、飞书（长连接）、钉钉（Stream）。三者都不需要公网地址。

借鉴 OpenClaw / AstrBot 的网关思路：渠道只负责收发，所有对话逻辑交给同一个 Bot → Agent。
借鉴 wealthpilot 的配对：每个渠道只认一个主人——本机生成配对码，从手机发给机器人才算绑定。
情感对话是最私密的数据，陌生人发来的消息一律不进 Agent。
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time

from answerlife import commands
from answerlife.agent import Agent
from answerlife.store import Store

log = logging.getLogger("answerlife.channel")
CHANNELS = {"telegram": "Telegram", "feishu": "飞书", "dingtalk": "钉钉"}
PAIR_TTL = 600


def split_text(text: str, size: int) -> list[str]:
    chunks, buf = [], ""
    for para in text.split("\n"):
        while len(para) > size:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(para[:size])
            para = para[size:]
        if len(buf) + len(para) + 1 > size:
            chunks.append(buf)
            buf = para
        else:
            buf = f"{buf}\n{para}" if buf else para
    if buf.strip():
        chunks.append(buf)
    return [c for c in chunks if c.strip()]


def new_pair_code(store: Store, channel: str) -> str:
    code = f"{secrets.randbelow(10**6):06d}"
    store.set(f"channel:{channel}:pair", {"code": code, "expires": time.time() + PAIR_TTL})
    return code


def _starter(name: str) -> str:
    from answerlife import skills as registry
    found = registry.discover().get(name)
    return (found.starter if found and found.starter else f"我想试试 {name}")


def owner(store: Store, channel: str) -> str | None:
    return (store.get(f"channel:{channel}:owner") or {}).get("chat_id")


class Bot:
    """一个渠道的机器人。api 需要实现 async send(chat_id, text)。"""

    def __init__(self, api, channel: str, store: Store, agent: Agent) -> None:
        self.api, self.channel, self.store, self.agent = api, channel, store, agent

    def _conv_key(self) -> str:
        return f"channel:{self.channel}:conv"

    async def message(self, chat_id: str | int, text: str) -> None:
        chat_id, text = str(chat_id), text.strip()
        if not text:
            return
        current = owner(self.store, self.channel)
        if current != chat_id:
            pair = self.store.get(f"channel:{self.channel}:pair") or {}
            if pair and pair.get("expires", 0) > time.time() and text.strip() == pair.get("code"):
                self.store.set(f"channel:{self.channel}:owner", {"chat_id": chat_id})
                self.store.delete_key(f"channel:{self.channel}:pair")
                await self.api.send(chat_id, "配对成功。之后在这里直接和我说话就好。\n\n" + commands.HELP)
            elif pair and current is None:
                pair["tries"] = pair.get("tries", 0) + 1     # 输错 5 次作废，防止被人猜
                if pair["tries"] >= 5:
                    self.store.delete_key(f"channel:{self.channel}:pair")
                else:
                    self.store.set(f"channel:{self.channel}:pair", pair)
                await self.api.send(chat_id, "配对码不对。请在电脑上重新运行 answerlife pair " + self.channel)
            elif current is None:
                await self.api.send(chat_id, "还没有配对。请在电脑上运行 answerlife pair "
                                    f"{self.channel}，把显示的 6 位数字发给我。")
            return   # 已有主人时，其他人的消息不回应
        reply = commands.handle(self.store, text)
        if reply == "__NEW__":
            self.store.delete_key(self._conv_key())
            await self.api.send(chat_id, "好，我们重新开始。今天有什么事，一直没从你脑子里过去？")
            return
        skill = None
        if reply and reply.startswith("__SKILL__:"):
            skill = reply.split(":", 1)[1]
            self.store.delete_key(self._conv_key())       # 一个 skill 开一段新对话
            text, reply = _starter(skill), None
        if reply is not None:
            await self.api.send(chat_id, reply)
            return
        conv = self.store.get(self._conv_key())
        result = await asyncio.to_thread(self.agent.respond, conv, text, self.channel, skill)
        self.store.set(self._conv_key(), result.conv_id)
        if result.safety_message:
            await self.api.send(chat_id, result.safety_message)
        await self.api.send(chat_id, result.text)

    async def push(self, text: str) -> bool:
        """主动发给主人（实验回访）。同时写进当前对话，模型下一轮能看到上下文。"""
        chat_id = owner(self.store, self.channel)
        if not chat_id:
            return False
        conv = self.store.get(self._conv_key())
        if not conv or not self.store.conversation(conv):
            conv = self.store.new_conversation(self.channel)
            self.store.set(self._conv_key(), conv)
        self.store.add_message(conv, "user", "（系统：七天实验到期，主动问候一次）")
        self.store.add_message(conv, "assistant", text)
        await self.api.send(chat_id, text)
        return True
