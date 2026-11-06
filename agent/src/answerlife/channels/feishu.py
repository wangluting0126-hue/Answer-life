"""飞书：收消息走官方 SDK 的长连接（不需要公网地址），发消息直接调开放平台接口。

需要在飞书开放平台建“企业自建应用”，开通机器人与收发消息权限，事件订阅选“使用长连接接收事件”，
订阅 im.message.receive_v1。安装：uv sync --extra feishu。
实现沿用 wealthpilot 的飞书渠道（同一套 SDK 用法）；本项目尚未用真实飞书应用跑过。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time

import httpx

from answerlife.channels import Bot, split_text

log = logging.getLogger("answerlife.channel.feishu")
CHUNK = 3500


class Feishu:
    def __init__(self, app_id: str, app_secret: str, base: str = "https://open.feishu.cn",
                 http: httpx.AsyncClient | None = None) -> None:
        self.app_id, self.app_secret, self.base = app_id, app_secret, base.rstrip("/")
        self.http = http or httpx.AsyncClient(timeout=15.0)
        self._token: tuple[str, float] = ("", 0.0)
        self.error = ""

    async def token(self) -> str:
        if self._token[1] > time.time() + 60:
            return self._token[0]
        resp = await self.http.post(f"{self.base}/open-apis/auth/v3/tenant_access_token/internal",
                                    json={"app_id": self.app_id, "app_secret": self.app_secret})
        data = resp.json()
        if data.get("code"):
            raise RuntimeError(f"飞书拒绝了应用凭证：{data.get('msg') or data.get('code')}")
        self._token = (data["tenant_access_token"], time.time() + int(data.get("expire") or 7200))
        return self._token[0]

    async def send(self, chat_id: str, text: str) -> None:
        token = await self.token()
        for chunk in split_text(text, CHUNK) or ["（空）"]:
            resp = await self.http.post(f"{self.base}/open-apis/im/v1/messages", params={"receive_id_type": "chat_id"},
                                        headers={"Authorization": f"Bearer {token}"},
                                        json={"receive_id": chat_id, "msg_type": "text",
                                              "content": json.dumps({"text": chunk}, ensure_ascii=False)})
            data = resp.json()
            if data.get("code"):
                raise RuntimeError(f"飞书没有接受这条消息：{data.get('msg') or data.get('code')}")


def parse_event(data) -> tuple[str, str, str] | None:
    """SDK 的“收到消息”事件 →（会话 ID, 文字, 消息 ID）。只处理单聊文字。"""
    message = getattr(getattr(data, "event", None), "message", None)
    if message is None or getattr(message, "message_type", "") != "text":
        return None
    if getattr(message, "chat_type", "p2p") != "p2p":
        return None
    try:
        text = str(json.loads(message.content or "{}").get("text") or "")
    except ValueError:
        return None
    text = re.sub(r"@_user_\d+\s*", "", text).strip()
    return (str(message.chat_id), text, str(message.message_id)) if message.chat_id and text else None


class Listener:
    def __init__(self, bot: Bot, loop: asyncio.AbstractEventLoop) -> None:
        self.bot, self.loop = bot, loop
        self.seen: list[str] = []

    def on_message(self, data) -> None:
        parsed = parse_event(data)
        if parsed is None:
            return
        chat_id, text, message_id = parsed
        if message_id in self.seen:          # 飞书没及时收到确认会重发
            return
        self.seen = [*self.seen[-200:], message_id]
        asyncio.run_coroutine_threadsafe(self.bot.message(chat_id, text), self.loop)

    def _run(self) -> None:
        api: Feishu = self.bot.api
        try:
            import lark_oapi as lark
            import lark_oapi.ws.client as ws_client

            # SDK 导入时把当前事件循环存成模块变量；主线程的循环在跑，给这个线程单独建一个
            ws_client.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(ws_client.loop)
            handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(self.on_message).build()
            lark.ws.Client(api.app_id, api.app_secret, event_handler=handler, domain=api.base,
                           log_level=lark.LogLevel.WARNING).start()
        except ImportError:
            api.error = "没有安装飞书 SDK：运行 uv sync --extra feishu"
        except Exception as e:  # noqa: BLE001
            api.error = f"飞书长连接断开：{e}"
        if api.error:
            log.warning("%s", api.error)

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self._run, daemon=True, name="al-feishu")
        thread.start()
        return thread
