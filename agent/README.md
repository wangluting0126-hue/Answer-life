# Answer Life Agent

这里是可运行的 Python Agent。网页、CLI 和可选的手机渠道共用技能、工具和本地数据。

在本目录运行：

```bash
uv sync --locked
ANSWERLIFE_HOME="$(mktemp -d)" AI_PROVIDER=mock AI_FALLBACK= uv run --locked answerlife serve
```

打开 <http://127.0.0.1:8020>，点击「翻一页书」后发送「测试出页」。

- [项目介绍与截图](../README.md)
- [安装、配置、命令和手机渠道](../docs/cli.md)
- [HTTP API 和可运行示例](../docs/api.md)
- [运行时架构](../docs/architecture.md)
- [本地开发与贡献](../CONTRIBUTING.md)
