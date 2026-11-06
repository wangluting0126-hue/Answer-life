<div align="center">

# 我的答案之书 · Answer Life

> 一个可以停一下的地方。

**本地运行的情绪陪伴 Agent：先听你说，再陪你做一件小事**

<sub>终端 · 网页 · Telegram / 飞书 / 钉钉 · 数据只在你的电脑上 · 自带模型 Key</sub>

</div>

---

## 它是什么

一本可以慢慢翻的书。首页用晚霞湖景做封面，画面向下淡入纸白；对话、记录和答案页用湖绿与墨色，标题用楷体，正文用宋体。首页的八只情绪鸟会动，聊天头像跟着你选的心情换，日历里也会出现对应的小鸟。右上角默认显示北京，点城市名可以改。

答案之书从具体经历讲起，再慢慢把事情想开。文风调研和示例见 [答案之书的表达笔记](docs/answer-book-voice.md)。

平时它就是陪你说话。你需要的时候，它会用下面这些技能陪你做一件具体的小事：

| 技能 | 用来做什么 |
|---|---|
| 情绪天气 | 给此刻的心情起一个更准确的名字，记一笔打卡，回看最近的起伏 |
| 先停一下 | 一分钟跟随式呼吸（跟着书页上的圆慢慢呼吸），或 5-4-3-2-1 着地练习 |
| 我的答案之书 | 用之前的 Answer-life skill 1.1：聊一件事，翻到一页有出处的书，留一件这周能试的小事 |
| 难开口的话 | 用非暴力沟通四步整理一段难说出口的话；只写草稿，从不替你发 |
| 换个角度 | 把脑子里那句最狠的话拿出来，按想法记录的步骤看一看 |
| 睡前三件小事 | 一天结束时找三件哪怕很小的好事 |
| 写给未来的信 | 封一封信给以后的自己，到日子送回给你 |

还会主动找你三件事（都可以在“我”里关掉）：晚安小结、未来信送达、七天实验回访。

## 设计参考

| 来源 | 借了什么 |
|---|---|
| [Life Designer](https://github.com/Jackychen-12/life-designer) | 纸面留白、先接住原话、用具体问题推进对话 |
| [Manus](https://manus.im) | 首页只留一个安静的大输入框 |
| [Memos](https://github.com/usememos/memos) | 日记、信、答案页、心情排成一条时间线 |
| [TadaPal](https://apps.apple.com/cn/app/id6744717070) | 伙伴随你的小行动给出反馈 |
| [OpenClaw](https://github.com/openclaw/openclaw) | Gateway 架构；skill 是带 frontmatter 的 SKILL.md，提示词里只放索引、用到才读全文；第三方 skill 视为不可信 |
| [Syll](https://thu-sage.github.io/syll/research.html) / Soul Protocol | 人格是一份人能直接改的纯文本（SOUL.md）；主动的陪伴仪式 |
| [EmoLLM](https://github.com/SmartFlowAI/EmoLLM) / [SoulChat](https://github.com/scutcyr/SoulChat) | 共情优先、不冒充治疗；危机识别规则先行 |
| [wealthpilot](https://github.com/Jackychen-12/wealthpilot) | 单进程 FastAPI + SQLite、终端/网页/IM 三入口、配对码、备用模型、自检 |

截图对比见 [docs/ui-references/](docs/ui-references/index.html)。

## 网页里的入口

- 首次打开可以填写个人资料。设置里的「我对你的了解」会用你填写的称呼和已经同意保存的记忆。
- 「记录」页可切换周报和月报。每份回看从一张有出处的书卡开始，再写这段时间的短札。
- 小鸟与羽毛的可复用素材包在 [小鸟动画](小鸟动画/)；网页实际使用的图片、GIF 和 WebP 都随 Agent 源码安装。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/)。

```bash
make setup
```

```bash
uv run answerlife setup
```

```bash
make start
```

`make start` 会打开终端对话，网页版同时运行在 <http://localhost:8020>，IM 渠道和陪伴节奏随进程运行。

不想填 Key，先看看样子：

```bash
make demo
```

### 模型

| AI_PROVIDER | 说明 |
|---|---|
| `anthropic`（默认） | Claude，默认 `claude-opus-5-5`、`ANTHROPIC_EFFORT=low`；系统提示词分段缓存，开启服务端 refusal fallback |
| `deepseek` | DeepSeek |
| `openai` | 任何兼容 OpenAI 接口、支持工具调用的服务：硅基流动、通义、Kimi、本机 Ollama…… |
| `mock` | 不联网，测试和演示用 |

`AI_FALLBACK` 可以设一个备用服务。完整配置见 [.env.example](.env.example)。

### 手机

在 `answerlife setup` 里填 Telegram Bot Token、飞书或钉钉应用凭证（三者都不需要公网地址），重启后：

```bash
uv run answerlife pair telegram
```

把显示的 6 位数字发给机器人即完成配对。每个渠道只认配对过的一个人，陌生人的消息一律不进 Agent。输错 5 次配对码作废。

IM 里可用：`/skills` 看技能、`/skill good-things` 直接开始、`/mood 7 有点累` 打卡、`/memory` 看记忆、`/forget 3` 删除、`/new` 新对话。

### 技能

```bash
uv run answerlife skills list
```

```bash
uv run answerlife skills install <目录或 git 地址>
```

技能就是一个含 `SKILL.md`（frontmatter 写 `name` / `description`）的目录，和 Claude Code、OpenClaw 用的格式一致；可选的 `meta.json` 给界面用（中文名、图标、颜色、开场白）。装进来的第三方技能只作为说明文字，**其中任何代码都不会执行**；带程序化工具的只有内置技能（见 `src/answerlife/skill_tools/`）。

## 安全与隐私

- **危机识别规则先行**：消息先过一遍确定性规则（`safety.py`）。命中自伤、轻生或正在受到伤害的信号时，固定的求助信息（全国心理援助热线 12356 等）一定会发出，即使模型不可用；这一轮不出答案页、不布置练习。
- **长期记录要同意**：记忆、日记、实验记录在第一次保存前会先问你；拒绝后不再保存。所有记录都能在网页上查看和删除，`/forget all` 一键清空。
- **只在本机**：数据在 `~/.answerlife/`（SQLite + 答案之书原生的 JSON 记录），服务默认只监听 127.0.0.1。
- 小鸟是 AI 陪伴，不是心理咨询或治疗，不做诊断。

## 结构

```
src/answerlife/
  agent.py         一轮对话：安全检查 → 系统提示词（SOUL + skill 索引 + 已激活 skill + 记忆）→ 工具循环
  llm.py           Claude / OpenAI 兼容 / mock，备用模型切换
  skills.py        skill 发现、启用、激活、安装
  skill_tools/     内置 skill 的程序化工具（答案之书出页、呼吸练习、未来信）
  tools.py         核心工具：use_skill、记忆、情绪打卡、日记
  emotions.py      情绪调色板与情绪地图
  safety.py        危机识别与求助信息
  routines.py      晚安小结、未来信送达、实验回访
  channels/        Telegram、飞书、钉钉
  server.py        FastAPI：网页、接口、IM、陪伴节奏
  web/index.html   网页（无构建步骤）
  skills/          7 个内置 skill（answer-book 为原 skill 原样）
```

## 现状

- 项目测试（`make test`）用 mock 模型运行，不联网。
- **真实模型冒烟测试（2026-11-05，DeepSeek `deepseek-chat`）**，四个场景全部按预期：

  | 场景 | 结果 |
  |---|---|
  | 倾诉失眠 → 用户说“记下来吧” | 先陪着问一句，没急着出页；用户同意后才调 `set_memory_consent` 和 `remember`，并开了 4-7-8 呼吸 |
  | “好慌，带我做一下呼吸” | 调 `start_breathing`（慢呼吸），网页弹出跟随动画 |
  | 答案之书“直接出页” | 查引文 → 读参考 → `create_answer_page` 一次校验失败后自行修正重试，出页约 10–20 秒；判据和七天实验具体可检验；已写入实验记录 |
  | “不想活了” | 规则命中 crisis，固定求助信息先发出；模型这一轮无工具，只问此刻是否安全、身边有没有人 |

  测试中发现并修复：出页时工具调用次数多，曾经用满步数却没有文字回复。现在步数上限 12，用满后最后一次请求禁止调工具、必须回话；仍为空时用出好的页兜底。
- **Claude 还没有用真实 Key 跑过**（代码按 Anthropic SDK 文档写，带分段提示词缓存和 refusal fallback）。
- 飞书、钉钉渠道沿用 wealthpilot 的实现，本项目尚未用真实应用验证；Telegram 同样只做了接口层测试。
- 企业微信（需要公网回调）、语音、MCP Server 还没做。
