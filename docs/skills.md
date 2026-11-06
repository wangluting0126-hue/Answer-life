# 使用和编写技能

仓库提供两种使用方式。

| 场景 | 入口 |
| --- | --- |
| 在 Answer Life 中运行 | 安装 Agent 后用 `answerlife skills list` 查看。终端或机器人里输入 `/skill answer-book`，网页点「翻一页书」。 |
| 在支持 Agent Skills 的其他客户端中复用 | 按客户端的安装方式导入整个 [answer-book 目录](../answer-book/)，保留 `SKILL.md`、参考资料、引文库和脚本。 |

Answer Life 自带[应用内答案之书](../agent/src/answerlife/skills/answer-book/)。在这个运行时里，查引文、出页、记录和回看由已注册的 Python 工具提供。其他客户端能否运行独立 Skill 的脚本、写入文件或安排提醒，取决于该客户端的能力和授权。

添加自己的技能时，先写一个含 `name`、`description` 的 `SKILL.md`，再运行：

```bash
answerlife skills install ./my-skill
answerlife skills list
answerlife chat
```

在对话里输入 `/skill my-skill`。注册器会把技能名和描述交给模型，激活时才加载正文。在 Answer Life 中，第三方技能作为说明和参考资料读取，运行时工具来自内置注册表。最小技能模板见[命令手册](cli.md#自定义技能)。

想看独立 Skill 的效果，可从[五组示例索引](../开始阅读.html)选择职业、时间、关系、专题卷宗或周回看。
