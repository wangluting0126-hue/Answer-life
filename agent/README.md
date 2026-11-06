# Answer Life Agent

> 有时候，你需要的只是把卡住的那一刻说出来。再读一页，看看下一步能不能小一点。

Answer Life 是单用户、本地运行的情绪陪伴 Agent。网页、终端和手机聊天共用一套技能和记录。你决定什么时候聊天、什么时候翻书，以及哪些事情值得留到下次。

[快速开始](#快速开始) · [能力](#能力) · [运行方式](#运行方式) · [开发与测试](#开发与测试)

## 能力

| 想做的事 | 入口和结果 |
| --- | --- |
| 先安静一下 | 在首页选一只情绪鸟，或用「先停一下」做一分钟呼吸。 |
| 理清一件事 | 「翻一页书」会从你的原话出发，找一段可核对的原文，留下一种异议和一件七天内能尝试的小事。 |
| 说一段难开口的话 | 「难开口的话」练习把情况、感受和请求说得具体。 |
| 换个角度想 | 记录一个念头，看看事实支持哪些解释。 |
| 给今天收个尾 | 记下睡前三件小事，或写一封到日期才打开的未来信。 |
| 回头看一眼 | 「记录」里有情绪日历、日记和答案页，也有从书卡起笔的周报、月报。 |
| 管理自己的资料 | 首访资料可以跳过。「我的」可以编辑资料、查看允许留下的记忆或删除记录。 |

## 快速开始

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。下面的命令都在 `agent/` 目录运行。

### 先跑一遍演示

```bash
uv sync --locked
ANSWERLIFE_HOME="$(mktemp -d)" AI_PROVIDER=mock AI_FALLBACK= uv run --locked answerlife serve
```

打开 <http://127.0.0.1:8020>，填写资料或跳过，在首页选一只鸟，再点「翻一页书」并发送「测试出页」。打开聊天里生成的答案页，然后到「记录」查看周报和月报。

### 接入自己的模型

```bash
uv run --locked answerlife setup
uv run --locked answerlife serve
```

在 `setup` 中选择提供商，并按终端提示填写 Key。也可用 [.env.example](.env.example) 配置本机的 `~/.answerlife/.env`。

| 提供商 | 配置 |
| --- | --- |
| DeepSeek | `AI_PROVIDER=deepseek`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL` |
| Claude | `AI_PROVIDER=anthropic`、`ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL` |
| OpenAI 兼容服务 | `AI_PROVIDER=openai`、`OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL` |
| 本地演示 | `AI_PROVIDER=mock` |

使用 DeepSeek 时，可以从 [官方支持的模型](https://api-docs.deepseek.com/) 中选一个支持工具调用的名称。验收真实模型时让 `AI_FALLBACK` 留空，便于确认实际提供商。

## 运行方式

| 命令 | 用途 |
| --- | --- |
| `uv run --locked answerlife` | 终端对话，同时启动网页和已配置的 IM |
| `uv run --locked answerlife chat` | 只开终端对话 |
| `uv run --locked answerlife serve` | 只开网页服务、接口和已配置的 IM |
| `uv run --locked answerlife doctor` | 检查模型配置、数据库和技能 |
| `uv run --locked answerlife skills list` | 查看可用技能 |
| `uv run --locked answerlife skills install <目录或仓库>` | 安装可读的 Skill 说明 |

Telegram、飞书和钉钉可以在 `setup` 中填写机器人凭证。飞书和钉钉先分别安装 `feishu`、`dingtalk` 可选依赖。服务运行后，用 `uv run --locked answerlife pair <渠道>` 生成六位配对码，再发给自己的机器人。

IM 内可用 `/skills`、`/skill good-things`、`/mood 7 有点累`、`/memory`、`/forget 3` 和 `/new`。未来信、晚安小结和实验回看提醒随服务运行，实际送达需要可用的已配对渠道。

## 一次翻页怎么完成

1. 网页或终端把对话交给同一个 [Agent](src/answerlife/agent.py)。安全层先判断是否需要暂停正常工具流程。
2. 模型接收已启用的技能与会话上下文，自行决定是否追问、激活技能和调用工具。
3. 答案页使用 [引文库](src/answerlife/skills/answer-book/quotes/) 的原文 ID，渲染器校验字段并生成 HTML、Markdown、JSON。
4. 答案页回到对话和时间线。用户允许保存长期记录后，可以留下实验并回看结果。周报、月报根据日期范围读取真实记录，再选书卡写短札。

应用默认监听本机。SQLite、生成的答案页和本机配置放在 `ANSWERLIFE_HOME`，默认目录为 `~/.answerlife`。网页个人资料和头像由浏览器本地保存。启用在线模型时，对话及相关上下文会交给配置的提供商。需要模型改写周报或月报时，由用户在报告页主动发起。

## 开发与测试

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest -q
uv run --locked python -B src/answerlife/skills/answer-book/scripts/verify.py
```

| 核验路径 | 核验点 |
| --- | --- |
| 应用回归 | 对话、工具、路由、配对契约、持久化、同意控制与安全分流 |
| Skill 检查 | 引文核验、字段校验、HTML 导出、回看边界和记录去重 |
| DeepSeek 实跑 | 隔离测试目录，关闭模型回退，通过 `/api/chat` 验证澄清、查引文与出页，再核对打卡、日记和周/月短札 |
| 网页素材 | 首页、情绪鸟、羽毛和报告尾图都随源码安装 |

网页由 [FastAPI](src/answerlife/server.py) 提供，界面在 [web/index.html](src/answerlife/web/index.html)。模型适配在 [llm.py](src/answerlife/llm.py)，本地数据在 [store.py](src/answerlife/store.py)，回看在 [reflections.py](src/answerlife/reflections.py)。

[文风和样本来源](docs/answer-book-voice.md) · [界面参考](docs/ui-references/index.html) · [小鸟与羽毛素材包](小鸟动画/)
