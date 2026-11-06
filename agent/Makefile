.PHONY: setup start serve install uninstall test doctor demo

setup:           ## 安装依赖（含飞书、钉钉 SDK）
	uv sync --extra dev --extra feishu --extra dingtalk
	@echo "✅ 安装完成。下一步：uv run answerlife setup，然后 make start"

start:           ## 终端对话 + 后台网页版（http://localhost:8020）+ IM
	uv run answerlife

serve:           ## 只开服务，适合常驻
	uv run answerlife serve

demo:            ## 不需要 Key 的演示（mock 模型，数据放在 /tmp）
	ANSWERLIFE_HOME=/tmp/answerlife-demo AI_PROVIDER=mock uv run answerlife

install:         ## 装成全局命令 answerlife
	@mkdir -p $(HOME)/.local/bin
	@printf '%s\n' '#!/bin/sh' 'exec "$(CURDIR)/.venv/bin/answerlife" "$$@"' > $(HOME)/.local/bin/answerlife
	@chmod +x $(HOME)/.local/bin/answerlife
	@echo "✅ 已安装到 ~/.local/bin/answerlife"

uninstall:
	@rm -f $(HOME)/.local/bin/answerlife

doctor:          ## 自检：模型、skill、数据库、IM
	uv run answerlife doctor

test:            ## 运行测试（mock 模型，不联网）
	uv run pytest -q
