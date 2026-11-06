"""模型层：Claude（Anthropic SDK）、任何兼容 OpenAI 接口的服务（DeepSeek、通义、Kimi、本机 Ollama……），
以及一个不联网的 mock（测试和演示用）。主模型出错时可以切到备用模型（AI_FALLBACK）。

每个实现只做一件事：给定系统提示词、历史消息和工具，跑完一轮工具循环，返回最终文字。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from answerlife.settings import Settings, get_settings

log = logging.getLogger("answerlife.llm")
MAX_STEPS = 12   # 出页可能要查引文、读参考、校验失败重试，给足步数
Runner = Callable[[str, dict], str]
Blocks = list[tuple[str, bool]]   # (系统提示词片段, 是否在其后放缓存断点)


@dataclass
class Result:
    text: str
    provider: str
    model: str
    refused: bool = False


class LLMError(RuntimeError):
    pass


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, s: Settings) -> None:
        import anthropic

        self.s = s
        self.model = s.anthropic_model
        self.client = anthropic.Anthropic()   # 凭证从 ANTHROPIC_API_KEY 或 `ant auth login` 读取

    def run(self, blocks: Blocks, history: list[dict], tools: list[dict], execute: Runner) -> Result:
        import anthropic

        system = [{"type": "text", "text": text, **({"cache_control": {"type": "ephemeral"}} if cache else {})}
                  for text, cache in blocks if text]
        messages: list = [{"role": m["role"], "content": m["content"]} for m in history]
        texts: list[str] = []
        for step in range(MAX_STEPS + 1):
            last = step == MAX_STEPS          # 工具用满了：最后一次不许再调工具，必须回一句话
            try:
                resp = self.client.beta.messages.create(
                    model=self.model, max_tokens=self.s.max_tokens, system=system, messages=messages,
                    **({"tools": tools} if tools else {}),
                    **({"tool_choice": {"type": "none"}} if last and tools else {}),
                    output_config={"effort": self.s.anthropic_effort},
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                )
            except anthropic.APIStatusError as e:
                raise LLMError(f"Claude 返回错误 {e.status_code}：{e.message}") from e
            except anthropic.APIConnectionError as e:
                raise LLMError(f"连不上 Claude：{e}") from e
            if resp.stop_reason == "refusal":
                return Result("这个话题我这次没法接着聊下去。如果你愿意，可以换个说法，或者告诉我你现在最需要的是什么。",
                              self.name, self.model, refused=True)
            texts += [b.text for b in resp.content if b.type == "text" and b.text.strip()]
            calls = [b for b in resp.content if b.type == "tool_use"]
            if last or resp.stop_reason != "tool_use" or not calls:
                break
            messages.append({"role": "assistant", "content": resp.content})   # 原样带回，含 thinking 块
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": c.id, "content": execute(c.name, c.input)} for c in calls]})
        return Result(_final(texts), self.name, resp.model or self.model)


class OpenAICompatLLM:
    """任何兼容 OpenAI chat.completions + function calling 的服务。"""

    def __init__(self, s: Settings, kind: str) -> None:
        from openai import OpenAI

        self.s, self.name = s, kind
        if kind == "deepseek":
            base, key, self.model = s.deepseek_base_url, s.deepseek_api_key, s.deepseek_model
        else:
            base, key, self.model = s.openai_base_url, s.openai_api_key or "none", s.openai_model
        if not self.model:
            raise LLMError(f"{kind} 没有配置模型名")
        self.client = OpenAI(base_url=base or None, api_key=key)

    def run(self, blocks: Blocks, history: list[dict], tools: list[dict], execute: Runner) -> Result:
        from openai import APIConnectionError, APIStatusError

        fn_tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                      "parameters": t["input_schema"]}} for t in tools]
        messages: list[dict] = [{"role": "system", "content": "\n\n".join(t for t, _ in blocks if t)}]
        messages += [{"role": m["role"], "content": m["content"]} for m in history]
        texts: list[str] = []
        for step in range(MAX_STEPS + 1):
            last = step == MAX_STEPS
            try:
                resp = self.client.chat.completions.create(model=self.model, messages=messages,
                                                           **({"tools": fn_tools} if fn_tools else {}),
                                                           **({"tool_choice": "none"} if last and fn_tools else {}),
                                                           max_tokens=min(self.s.max_tokens, 8192))
            except APIStatusError as e:
                raise LLMError(f"{self.name} 返回错误 {e.status_code}：{e.message}") from e
            except APIConnectionError as e:
                raise LLMError(f"连不上 {self.name}：{e}") from e
            msg = resp.choices[0].message
            if msg.content and msg.content.strip():
                texts.append(msg.content)
            if last or not msg.tool_calls:
                break
            messages.append({"role": "assistant", "content": msg.content or "",
                             "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except ValueError:
                    out = json.dumps({"error": "参数不是合法 JSON"}, ensure_ascii=False)
                else:
                    out = execute(tc.function.name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
        return Result(_final(texts), self.name, self.model)


class MockLLM:
    """不联网的模拟模型：测试与演示用。说“测试出页”会走一遍真实的出页工具。"""

    name, model = "mock", "mock"

    def run(self, blocks: Blocks, history: list[dict], tools: list[dict], execute: Runner) -> Result:
        dynamic = blocks[-1][0] if blocks else ""
        last = history[-1]["content"] if history else ""
        if "测试出页" in last:
            from answerlife.settings import SKILL_DIR, today

            page = json.loads((SKILL_DIR / "examples" / "career.json").read_text(encoding="utf-8"))
            page["date"] = today()
            page["origin"] = "这是用虚构故事翻出的示范页。" + page["origin"]
            execute("use_skill", {"name": "answer-book"})
            out = json.loads(execute("create_answer_page", {"page": page}))
            return Result((f"给你翻了一页示范。\n{out['url']}" if out.get("ok") else "这页还没写好，过会儿再试一次。"), self.name, self.model)
        if "呼吸" in last:
            execute("use_skill", {"name": "calm-breath"})
            execute("start_breathing", {"pattern": "slow"})
            return Result("我们一起慢下来。跟着圆圈，吸气四拍，呼气六拍。", self.name, self.model)
        if "写信" in last:
            import datetime as _dt
            from answerlife.settings import today as _today
            day = (_dt.date.fromisoformat(_today()) + _dt.timedelta(days=30)).isoformat()
            out = json.loads(execute("seal_letter", {"deliver_on": day, "title": "给一个月后的我", "content": last}))
            return Result(f"信封好了，{day} 送回给你。{out.get('error', '')}", self.name, self.model)
        if "打卡" in last:
            execute("log_mood", {"score": 6, "words": "模拟打卡"})
            return Result("记下了，今天 6 分。", self.name, self.model)
        if "【安全模式】" in dynamic:
            return Result("我在这里。此刻你安全吗？身边有没有可以马上联系的人？", self.name, self.model)
        return Result(f"（mock 演示）可以先发「测试出页」，看看成品长什么样。", self.name, self.model)


EMPTY = "（这一轮没有生成文字回复）"


def _final(texts: list[str]) -> str:
    return "\n\n".join(t.strip() for t in texts if t.strip()) or EMPTY


def build(kind: str, s: Settings):
    if kind == "anthropic":
        return AnthropicLLM(s)
    if kind in ("openai", "deepseek"):
        return OpenAICompatLLM(s, kind)
    if kind == "mock":
        return MockLLM()
    raise LLMError(f"不认识的 AI_PROVIDER：{kind}")


def run(blocks: Blocks, history: list[dict], tools: list[dict], execute: Runner) -> Result:
    s = get_settings()
    chain = [s.provider] + ([s.fallback] if s.fallback and s.fallback != s.provider else [])
    errors = []
    for kind in chain:
        try:
            return build(kind, s).run(blocks, history, tools, execute)
        except LLMError as e:
            log.warning("%s 不可用：%s", kind, e)
            errors.append(f"{kind}：{e}")
        except Exception as e:  # noqa: BLE001  凭证缺失等初始化错误
            log.warning("%s 初始化失败：%s", kind, e)
            errors.append(f"{kind}：{e}")
    raise LLMError("；".join(errors))
