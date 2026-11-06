# Answer Life 使用手册

[文档导航](README.md) · [项目介绍和截图](../README.md) · [安装](#安装) · [命令](#终端命令) · [手机渠道](#接入手机渠道) · [自定义技能](#自定义技能) · [测试](#开发与测试)

## 安装

需要 Git、Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。从仓库根目录安装独立命令。

```bash
uv tool install ./agent
uv tool update-shell
```

重新打开终端，运行 `answerlife --help`。如果从源码开发，在 `agent/` 里运行 `uv sync --locked`，然后把下文的 `answerlife` 换成 `uv run --locked answerlife`。

## 第一次使用

```bash
answerlife setup
answerlife doctor
answerlife serve
```

1. 配置时选择 `deepseek`，按提示输入自己的 Key，模型名称用账户可调用且支持工具调用的模型。手机渠道可先跳过。
2. 自检会向模型发一条简短的连通性请求，同时检查本地数据库与引文库。
3. 启动后打开 <http://127.0.0.1:8020>。填写名字或跳过，选一只情绪鸟，再点「翻一页书」说一件具体的事。生成后可点击对话中的答案卡。
4. 在「记录」里找答案页、日记、信和心情，进入周报或月报。在「我的」管理资料、长期记忆授权和提醒。

想先体验时，运行下面的命令并在网页里发送「测试出页」。

```bash
ANSWERLIFE_HOME="$(mktemp -d)" AI_PROVIDER=mock AI_FALLBACK= answerlife serve
```

### 模型配置

`setup` 写入 `~/.answerlife/.env`。也可以按 [配置示例](../agent/.env.example) 编辑该文件。进程环境变量优先于文件配置，修改后重启服务。

| 提供商 | 主要配置 |
| --- | --- |
| DeepSeek | `AI_PROVIDER=deepseek`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL` |
| Anthropic | `AI_PROVIDER=anthropic`、`ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL` |
| OpenAI 兼容接口 | `AI_PROVIDER=openai`、`OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL` |
| 本地演示 | `AI_PROVIDER=mock` |

验收某个提供商时，将 `AI_FALLBACK` 留空，便于判断请求实际落到了哪里。

## 终端命令

| 命令 | 用途 |
| --- | --- |
| `answerlife --help` | 显示可用子命令 |
| `answerlife --version` | 查看安装的版本 |
| `answerlife setup` | 配置模型和渠道 |
| `answerlife doctor` | 检查数据库、引文库和模型连通性 |
| `answerlife` | 开启终端对话，同时运行网页和已配置的渠道 |
| `answerlife chat` | 只开终端对话 |
| `answerlife serve` | 开启网页、API、已配置的渠道和提醒循环 |
| `answerlife serve --port 8021` | 在指定端口启动 |
| `answerlife pair telegram` | 生成一次性机器人配对码，渠道也可选 `feishu` 或 `dingtalk` |
| `answerlife skills list` | 查看内置与已安装的技能 |
| `answerlife skills install ./my-skill` | 从目录安装，也可传入含一个技能的 Git 仓库地址 |
| `answerlife skills remove my-skill` | 移除已安装技能，内置技能在网页「我的」停用 |

端口改变时，推荐用 `PORT=8021 answerlife serve`，让监听端口和生成的答案页链接使用同一个端口。服务默认在 `127.0.0.1` 监听，可通过 `/health` 检查服务，通过 `/docs` 查看 API。

### 对话内命令

下列命令输入到终端对话或已配对的机器人。

| 输入 | 效果 |
| --- | --- |
| `/help` | 查看对话内帮助 |
| `/skills` | 列出当前启用的技能 |
| `/skill answer-book` | 开启一次翻书对话 |
| `/skill calm-breath` | 开启呼吸练习 |
| `/mood 7 有点累` | 记录一次 1 到 10 分的心情 |
| `/moods` | 查看近 14 天打卡 |
| `/pages` | 查看最近生成的答案页 |
| `/consent on` 或 `/consent off` | 同意或停止之后的长期记忆保存 |
| `/memory` 与 `/forget 3` | 查看记忆与删除指定条目 |
| `/new` | 开始新会话 |
| `/status` | 查看当前模型和数据目录 |
| `/quit` | 退出终端对话 |

## 接入手机渠道

Telegram 随基础安装提供。飞书和钉钉需要额外依赖，可以从仓库根目录按需安装。

```bash
uv tool install --force './agent[feishu]'
# 也可以选择钉钉
uv tool install --force './agent[dingtalk]'
```

1. 在相应平台准备自己的机器人，运行 `answerlife setup`，选择配置手机渠道并填写所需凭证。
2. 启动 `answerlife serve`。保持服务运行，在另一个终端执行 `answerlife pair telegram`，或替换成对应渠道。
3. 10 分钟内把生成的 6 位数字发给自己的机器人，再发 `/help` 确认可用。
4. 「我的」可以配置晚安小结、未来信和实验回看。发送依赖服务持续运行、渠道可用且已经配对。默认生成的本地网页链接在运行服务的电脑上打开。

## 自定义技能

技能目录的入口是 `SKILL.md`，开头有小写字母、数字和连字符组成的 `name`，以及用于判断何时调用的 `description`。下面是一份可以复制的最小示例。

```bash
mkdir -p my-skill
cat > my-skill/SKILL.md <<'SKILL'
---
name: my-skill
description: 用户想把一件拖延的小事拆成十分钟能试的动作时使用。
---

先问清想做的事和卡住的地方，再给一个十分钟内能尝试的动作。
SKILL
answerlife skills install ./my-skill
answerlife skills list
answerlife chat
```

进入对话后输入 `/skill my-skill`。已安装技能在 `~/.answerlife/skills/`，同名时用户版本优先。第三方技能作为说明文字及参考资料读取，运行工具由 Agent 内置注册。应用已经自带 `answer-book`，独立版及其可读示例也随仓库提供。[独立 Skill](../answer-book/)

## 数据在哪

| 路径 | 内容 |
| --- | --- |
| `~/.answerlife/.env` | 模型和渠道配置 |
| `~/.answerlife/answerlife.db` | 会话、心情、记忆、日记、未来信和页面索引 |
| `~/.answerlife/pages/` | HTML、Markdown 和 JSON 答案页 |
| `~/.answerlife/book/` | 经授权保存的七天实验记录 |
| `~/.answerlife/skills/` | 用户安装的技能 |

用 `ANSWERLIFE_HOME` 可以切换整套数据目录。网页个人资料和头像保存在当前浏览器。在线模型接收回答所需的上下文，周报月报只有点击重写时才发送该次回看素材。回看页面当前会在刷新后回到本地短札。

## 开发与测试

在 `agent/` 运行。

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest -q
uv run --locked python -B src/answerlife/skills/answer-book/scripts/verify.py
```

应用测试覆盖 Agent 编排、工具、存储、同意控制和路由。Skill 校验检查引文、页面和实验记录。浏览器验收另用隔离数据跑过真实 DeepSeek，验证了从首页进对话、出页、保存、回看与配置的流程。外部 IM 消息和提醒送达需另用实际机器人验证。

[文风和样本来源](../agent/docs/answer-book-voice.md) · [实测截图](../agent/docs/demo/) · [界面参考](../agent/docs/ui-references/index.html)
