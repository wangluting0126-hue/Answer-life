# 从代码调用 Answer Life

运行 `answerlife serve` 后，CLI、网页和你自己的客户端都可以使用同一套本地数据。默认地址为 `http://127.0.0.1:8020`。交互式接口文档在 `/docs`，OpenAPI 描述在 `/openapi.json`。

## 运行一个独立的演示实例

在已安装 `answerlife` 的终端运行：

```bash
ANSWERLIFE_HOME="$(mktemp -d)" AI_PROVIDER=mock AI_FALLBACK= answerlife serve
```

在另一个终端检查服务并发送一条能触发演示答案页的消息：

```bash
curl -fsS http://127.0.0.1:8020/health
curl -fsS http://127.0.0.1:8020/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"text":"测试出页","skill":"answer-book"}'
```

也可以从仓库根目录运行无第三方依赖的 [Python 示例](../examples/chat.py)：

```bash
python3 examples/chat.py '测试出页' --skill answer-book
```

真实对话用 `answerlife setup` 配置模型后启动常规实例。首次请求发送 `text`，也可以带 `skill` 指定启用的技能。把返回的 `conversation_id` 放进下一次请求，就能续上同一段对话：

```bash
python3 examples/chat.py '我想再说说刚才那件事' --conversation-id '上次返回的会话ID'
```

## 读取响应

| 字段 | 客户端怎么用 |
| --- | --- |
| `reply` | 显示用户可读的回复 |
| `conversation_id` | 留给下一轮请求 |
| `pages` | 有成品时显示答案卡，使用条目的 `url` 打开页面。回复也可能只是追问，此时列表为空 |
| `events` | 读取工具结果事件，例如呼吸引导、保存记录或激活技能 |
| `skills`、`provider` | 展示当前技能或核对本轮使用的模型 |
| `safety`、`safety_message` | 有安全提示时连同回复展示 |
| `error` | 模型失败时可能仍返回 HTTP 200，客户端需要检查这个字段 |

`/api/chat` 也处理打卡等斜杠命令。直接处理的命令有 `command: true`，响应可能只有 `reply` 和会话 ID。`/new` 返回 `new: true`，客户端应清除当前会话 ID。空白消息会得到 HTTP 400，请求字段格式不符合接口时会得到 HTTP 422。

## 常用端点

| 路径 | 用途 |
| --- | --- |
| `GET /health` · `GET /api/status` | 检查进程、模型配置和渠道状态 |
| `GET /api/skills` | 枚举可用技能和启用状态 |
| `POST /api/chat` · `GET /api/conversations/{cid}` | 开启或续接对话，回读完整会话 |
| `POST /api/mood` · `GET /api/emotions` | 记下情绪并查看统计 |
| `GET /api/pages` · `GET /pages/{filename}` | 列出答案页或打开具体成品 |
| `GET /api/reflections/week` · `GET /api/reflections/month` | 读取周期内的书卡和本地短札 |
| `POST /api/reflections/week` · `POST /api/reflections/month` | 通过已配置的模型重写短札 |
| `PUT /api/settings` | 更新长期记忆授权等设置 |

HTTP 接口面向本机单用户，当前没有独立的 Web 身份验证。保持默认回环地址。开发和集成测试可用独立的 `ANSWERLIFE_HOME`，避免将测试对话写入日常记录。
