"""先停一下：呼吸练习。网页里弹出跟着呼吸的动画，终端和 IM 收到文字步骤。"""

from __future__ import annotations

SKILL = "calm-breath"

PATTERNS = {
    "slow": {"title": "慢呼吸", "steps": [["吸气", 4], ["呼气", 6]], "rounds": 6,
             "text": "用鼻子慢慢吸气，心里数 1、2、3、4；再用嘴慢慢呼气，数到 6。这样做六轮，大约一分钟。"},
    "box": {"title": "方块呼吸", "steps": [["吸气", 4], ["屏住", 4], ["呼气", 4], ["停一下", 4]], "rounds": 4,
            "text": "吸气 4 拍，屏住 4 拍，呼气 4 拍，停 4 拍，像沿着一个方块走一圈。走四圈。"},
    "478": {"title": "4-7-8 呼吸", "steps": [["吸气", 4], ["屏住", 7], ["呼气", 8]], "rounds": 4,
            "text": "吸气 4 拍，屏住 7 拍，慢慢呼气 8 拍。做四轮；如果屏气让你不舒服，就换成慢呼吸。"},
}

SPECS = [
    {"name": "start_breathing",
     "description": "先停一下：开始一段跟随式呼吸练习。slow 最温和，适合大多数时候；box 适合需要集中注意力；478 适合睡前。",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string", "enum": list(PATTERNS)}},
                      "required": ["pattern"]}},
]


def start_breathing(ctx, pattern: str = "slow") -> dict:
    p = PATTERNS.get(pattern, PATTERNS["slow"])
    ctx.emit("breathing", pattern=pattern, title=p["title"], steps=p["steps"], rounds=p["rounds"])
    return {"ok": True, "title": p["title"], "text_steps": p["text"],
            "note": "网页端会弹出呼吸动画；终端和 IM 里请把 text_steps 用你自己的话简短说给用户。练完问一句现在感觉怎样。"}
