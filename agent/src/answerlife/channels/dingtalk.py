"""钉钉：Stream 模式收消息（不需要公网地址），开放平台接口发消息。只认单聊。

需要企业内部应用 + 机器人（Stream 模式）。安装：uv sync --extra dingtalk。
实现沿用 wealthpilot 的钉钉渠道；本项目尚未用真实钉钉应用跑过。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import warnings

import httpx

from answerlife.channels import Bot, split_text

log = logging.getLogger("answerlife.channel.dingtalk")
CHUNK = 3500


class DingTalk:
    def __init__(self, client_id: str, client_secret: str, base: str = "https://api.dingtalk.com",
                 http: httpx.AsyncClient | None = None) -> None:
        self.client_id, self.client_secret, self.base = client_id, client_secret, base.rstrip("/")
        self.http = http or httpx.AsyncClient(timeout=15.0)
        self.robot_code = client_id
        self._token: tuple[str, float] = ("", 0.0)
        self.error = ""

    async def token(self) -> str:
        if self._token[1] > time.time() + 60:
            return self._token[0]
        resp = await self.http.post(f"{self.base}/v1.0/oauth2/accessToken",
                                    json={"appKey": self.client_id, "appSecret": self.client_secret})
        data = resp.json()
        if resp.status_code >= 400 or not data.get("accessToken"):
            raise RuntimeError(f"钉钉拒绝了应用凭证：{data.get('message') or resp.status_code}")
        self._token = (data["accessToken"], time.time() + int(data.get("expireIn") or 7200))
        return self._token[0]

    async def send(self, chat_id: str, text: str) -> None:
        token = await self.token()
        for chunk in split_text(text, CHUNK) or ["（空）"]:
            resp = await self.http.post(f"{self.base}/v1.0/robot/oToMessages/batchSend",
                                        headers={"x-acs-dingtalk-access-token": token},
                                        json={"robotCode": self.robot_code, "userIds": [str(chat_id)], "msgKey": "sampleText",
                                              "msgParam": json.dumps({"content": chunk}, ensure_ascii=False)})
            if resp.status_code >= 400:
                raise RuntimeError(f"钉钉没有接受这条消息：{resp.text[:200]}")


def parse_event(data: dict) -> tuple[str, str] | None:
    """“机器人收到消息”回调 →（发消息的人, 文字）。群聊、非文字返回 None。"""
    if not isinstance(data, dict) or str(data.get("conversationType")) != "1" or data.get("msgtype") != "text":
        return None
    sender = str(data.get("senderStaffId") or "").strip()
    text = str((data.get("text") or {}).get("content") or "").strip()
    return (sender, text) if sender and text else None


def start(bot: Bot, loop: asyncio.AbstractEventLoop) -> threading.Thread | None:
    api: DingTalk = bot.api
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import dingtalk_stream
    except ImportError:
        api.error = "没有安装钉钉 SDK：运行 uv sync --extra dingtalk"
        log.warning("%s", api.error)
        return None

    class Handler(dingtalk_stream.ChatbotHandler):
        async def process(self, callback):
            data = getattr(callback, "data", None) or {}
            if data.get("robotCode"):
                api.robot_code = data["robotCode"]
            parsed = parse_event(data)
            if parsed:   # 回复要几十秒：交给主循环，立刻应答回调，否则钉钉会重发
                asyncio.run_coroutine_threadsafe(bot.message(*parsed), loop)
            return dingtalk_stream.AckMessage.STATUS_OK, "OK"

    client = dingtalk_stream.DingTalkStreamClient(dingtalk_stream.Credential(api.client_id, api.client_secret))
    client.register_callback_handler(dingtalk_stream.ChatbotMessage.TOPIC, Handler())

    def serve() -> None:
        try:
            asyncio.run(client.start())
        except Exception as e:  # noqa: BLE001
            api.error = f"钉钉长连接断开：{e}"
            log.warning("%s", api.error)

    thread = threading.Thread(target=serve, daemon=True, name="al-dingtalk")
    thread.start()
    return thread
