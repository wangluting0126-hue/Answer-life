# 贡献指南

欢迎贡献复现案例、文档、技能、引文核验和 Agent 功能。提交前可以先看[架构](docs/architecture.md)和[文档导航](docs/)。

## 开发与验证

```bash
git clone https://github.com/wangluting0126-hue/Answer-life.git
cd Answer-life/agent
uv sync --locked --extra dev
uv run --locked --extra dev pytest -q
uv run --locked python -B src/answerlife/skills/answer-book/scripts/verify.py
```

页面或对话改动可用临时数据运行网页：

```bash
ANSWERLIFE_HOME="$(mktemp -d)" AI_PROVIDER=mock AI_FALLBACK= uv run --locked answerlife serve
```

- 提问题时写出操作路径、预期结果和实际结果。报告模型问题时，补充模型名和可分享的虚构输入。
- 提交 PR 时说明变化、测试结果，以及是否影响已有数据或调用方式。UI 改动附实际运行截图。
- 修改引文时保留原文、来源和核验依据。修改技能时，用至少一个真实任务形状的虚构案例检查它何时应激活、能调用什么、最终交付什么。
- 复现和截图用独立数据目录。共享日志和示例前，检查它们只包含可公开的测试数据。

首次贡献可以从[浏览器实测发现](README.md#验收与下一步)中的保存和文字准确性问题入手。
