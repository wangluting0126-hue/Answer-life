"""Keep a short, shared voice guide and trim a few known canned lines."""

from __future__ import annotations

import re

GUIDE = """# 说话像在桌边聊天
先接住对方说过的一处细节，再给一个现在就用得上的观察。用短句和具体动词。两三个自然段就够，一轮最多问一个会改变下一步的问题。
少说“判据、取样、反馈闭环、当前情境、用户”，多说“怎么看、试一下、回来说说、这件事、你”。小标题也用人会说的话。不要为了显得亲近而假装知道对方没说过的感受。
别用“我理解你的感受”“感谢你的分享”“基于以上分析”“不构成建议”起手，也别在每段结尾补一条免责句。求职例子：用“你用同一份简历投了三种岗位。挑一个你最想去的，把要求和做过的事摆在一起。哪一项空着，就从那里看。”
少写“不能保证面试”之类人人都知道的退路。有必要交代未知时，说清这次具体缺什么：“没看过那份简历，先不猜为什么没回音。”真实的安全、医疗等边界仍然要说明，不用一句套话带过。
想直接读成品，就停下追问。把书放在对方的事旁边：先说它照到了哪里，再给一件小事。不要把后台运行、工具调用、缓存或出页校验念给对方听。
"""

_CANNED = re.compile(
    r"这份对照只能帮助选择下一步[，,\s]*不能保证面试[。！]?"
    r"|不承诺面试[，,]也不能用少量结果证明因果[。！]?"
)
_OPENERS = re.compile(r"^(?:我理解你的感受|感谢你的分享|基于以上分析)[，。！：]\s*")


def polish(text: str) -> str:
    """Edit generated prose only; do not apply this to user text or book quotations."""
    cleaned = _CANNED.sub("先看看这份对照里，哪一处值得改。", text)
    return _OPENERS.sub("", cleaned).strip() or text


def page_copy(data: dict) -> dict:
    """Polish model-authored paragraphs without touching evidence or source IDs."""
    if "pages" in data and isinstance(data["pages"], list):
        return {**data, "pages": [page_copy(p) if isinstance(p, dict) else p for p in data["pages"]]}
    fields = {"title", "origin", "gloss", "context_note", "criterion", "action", "question", "dissent"}
    return {key: polish(value) if key in fields and isinstance(value, str) else value for key, value in data.items()}
