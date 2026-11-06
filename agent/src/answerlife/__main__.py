"""命令行入口。

answerlife              终端对话，端口空闲时同时启动网页和 IM 渠道
answerlife chat         只开终端对话
answerlife serve        只开服务（网页 + 接口 + IM + 实验回访），适合常驻
answerlife setup        引导配置模型与 IM，写到数据目录的 .env
answerlife skills       查看 / 安装 / 移除 skill
answerlife pair telegram|feishu|dingtalk   生成配对码
answerlife doctor       自检
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import socket
import sys
import threading
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

from rich.console import Console
from rich.panel import Panel

from answerlife import __version__

console = Console()


def _banner() -> None:
    from answerlife.settings import get_settings
    s = get_settings()
    model = {"anthropic": s.anthropic_model, "deepseek": s.deepseek_model}.get(s.provider, s.openai_model or s.provider)
    console.print(Panel.fit("[bold]我的答案之书[/] · 一个可以停一下的地方。\n"
                            f"[dim]模型 {s.provider} · {model}　数据 {s.home}　/help 查看命令　Ctrl+D 退出[/]",
                            border_style="blue"))


def _matches_local_web(host: str, port: int, data_home: str) -> bool:
    local_host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
    if ":" in local_host:
        local_host = f"[{local_host}]"
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(f"http://{local_host}:{port}/api/status", timeout=0.8) as response:
            status = json.load(response)
    except (OSError, ValueError):
        return False
    return isinstance(status, dict) and (
        status.get("app"), status.get("version"), status.get("home")
    ) == ("answerlife", __version__, data_home)


def _web_entry_url(base_url: str) -> str:
    from answerlife.settings import PACKAGE

    revision = hashlib.sha256((PACKAGE / "web" / "index.html").read_bytes()).hexdigest()[:12]
    url = urlsplit(base_url)
    query = f"{url.query}&ui={revision}" if url.query else f"ui={revision}"
    return url._replace(path=url.path or "/", query=query).geturl()


def chat(with_server: bool) -> None:
    from answerlife import commands
    from answerlife.settings import get_settings

    settings = get_settings()
    listener = None
    web_url = None
    if with_server:
        family = socket.AF_INET6 if ":" in settings.host else socket.AF_INET
        try:
            listener = socket.create_server((settings.host, settings.port), family=family)
        except OSError as error:
            if error.errno != errno.EADDRINUSE:
                raise
            if _matches_local_web(settings.host, settings.port, str(settings.home)):
                web_url = settings.base_url
                console.print(f"[dim]网页版已在 {settings.port} 运行，继续进入终端对话。[/]")
            else:
                console.print(f"[yellow]端口 {settings.port} 已被其他服务占用。已开启终端对话。[/]")

    if listener is not None:
        from answerlife import server
        store, agent = server.rt().store, server.rt().agent
        threading.Thread(target=server.serve, kwargs={"listener": listener},
                         daemon=True, name="al-server").start()
        web_url = settings.base_url
    else:
        from answerlife.agent import Agent
        from answerlife.store import Store
        store = Store(settings.db_path)
        agent = Agent(store)
    _banner()
    if web_url:
        console.print(f"[dim]网页版：{_web_entry_url(web_url)}[/]")
    console.print("\n[italic]今天过得怎么样？想说什么都可以。发 /skills 看看我会的几件事。[/]\n")
    conv = None
    while True:
        try:
            text = console.input("[bold blue]你 ›[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]下次见。[/]")
            return
        if not text:
            continue
        if text in ("/quit", "/exit", "退出"):
            return
        reply = commands.handle(store, text)
        if reply == "__NEW__":
            conv = None
            console.print("[dim]好，我们重新开始。[/]\n")
            continue
        skill = None
        if reply and reply.startswith("__SKILL__:"):
            from answerlife.channels import _starter
            skill, conv = reply.split(":", 1)[1], None
            text, reply = _starter(skill), None
            console.print(f"[dim]（开始：{text}）[/]")
        if reply is not None:
            console.print(reply + "\n")
            continue
        with console.status("[dim]正在想……[/]"):
            r = agent.respond(conv, text, "cli", skill)
        conv = r.conv_id
        if r.safety_message:
            console.print(Panel(r.safety_message, border_style="red"))
        console.print(f"\n{r.text}\n")
        for p in r.pages:
            console.print(Panel(f"{p['title']}\n[dim]{p['criterion']}[/]\n\n打开：{p['path']}", title="一页答案",
                                border_style="blue"))


def setup() -> None:
    from answerlife.settings import home

    path = home() / ".env"
    current = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                current[k.strip()] = v.strip()

    def ask(key: str, prompt: str, default: str = "", secret: bool = False) -> None:
        old = current.get(key, default)
        shown = ("已填写" if old else "") if secret else old
        value = console.input(f"{prompt}" + (f" [dim]（{shown}）[/]" if shown else "") + "：", password=secret).strip()
        if value:
            current[key] = value
        elif old:
            current[key] = old

    console.print(Panel.fit("配置答案之书 Agent。直接回车保留括号里的值。", border_style="blue"))
    ask("AI_PROVIDER", "模型服务 anthropic / deepseek / openai（兼容接口）/ mock", "anthropic")
    provider = current.get("AI_PROVIDER", "anthropic")
    if provider == "anthropic":
        ask("ANTHROPIC_API_KEY", "Anthropic API Key（已运行过 ant auth login 可留空）", secret=True)
        ask("ANTHROPIC_MODEL", "模型", "claude-opus-5-5")
    elif provider == "deepseek":
        ask("DEEPSEEK_API_KEY", "DeepSeek API Key", secret=True)
        ask("DEEPSEEK_MODEL", "模型", "deepseek-chat")
    elif provider == "openai":
        ask("OPENAI_BASE_URL", "接口地址（如 https://api.siliconflow.cn/v1、http://localhost:11434/v1）")
        ask("OPENAI_API_KEY", "API Key（本机模型可留空）", secret=True)
        ask("OPENAI_MODEL", "模型名（需支持工具调用）")
    ask("AI_FALLBACK", "备用模型服务（可留空）")
    if console.input("配置手机 IM 吗？[y/N]：").strip().lower() == "y":
        ask("TELEGRAM_BOT_TOKEN", "Telegram Bot Token（找 @BotFather 创建，可留空）", secret=True)
        ask("FEISHU_APP_ID", "飞书 App ID（可留空）")
        if current.get("FEISHU_APP_ID"):
            ask("FEISHU_APP_SECRET", "飞书 App Secret", secret=True)
        ask("DINGTALK_CLIENT_ID", "钉钉 Client ID（可留空）")
        if current.get("DINGTALK_CLIENT_ID"):
            ask("DINGTALK_CLIENT_SECRET", "钉钉 Client Secret", secret=True)
    path.write_text("\n".join(f"{k}={v}" for k, v in current.items() if v) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    console.print(f"[green]已保存到 {path}[/]。运行 [bold]answerlife[/] 开始。")


def pair(channel: str) -> None:
    from answerlife.channels import CHANNELS, new_pair_code
    from answerlife.settings import get_settings
    from answerlife.store import Store

    if channel not in CHANNELS:
        console.print(f"渠道只能是：{', '.join(CHANNELS)}")
        sys.exit(2)
    code = new_pair_code(Store(get_settings().db_path), channel)
    console.print(f"在{CHANNELS[channel]}里把这 6 位数字发给机器人（10 分钟内有效，需要 answerlife 在运行）：\n\n"
                  f"    [bold blue]{code}[/]\n")


def doctor() -> int:
    from answerlife import book, llm, soul
    from answerlife.settings import get_settings
    from answerlife.store import Store

    s = get_settings()
    ok = True

    def line(good: bool, label: str, detail: str = "") -> None:
        nonlocal ok
        ok = ok and good
        console.print(("[green]✓[/] " if good else "[red]✗[/] ") + label + (f"  [dim]{detail}[/]" if detail else ""))

    line(True, "数据目录", str(s.home))
    try:
        Store(s.db_path)
        line(True, "数据库", str(s.db_path))
    except Exception as e:  # noqa: BLE001
        line(False, "数据库", str(e))
    try:
        quotes = book.ab().bank()
        usable = sum(1 for q in quotes.values() if q.get("verified") is True and not q.get("blocked"))
        line(True, "答案之书 skill", f"{len(quotes)} 条引文，{usable} 条可用")
    except Exception as e:  # noqa: BLE001
        line(False, "答案之书 skill", str(e))
    try:
        r = llm.run([(soul.soul(), False), ("这是一次连通性自检。", False)], [{"role": "user", "content": "只回复：通"}], [],
                    lambda n, a: "{}")
        line(True, f"模型 {r.provider}:{r.model}", r.text[:40])
    except Exception as e:  # noqa: BLE001
        line(False, f"模型 {s.provider}", str(e)[:200])
    for name, configured in (("Telegram", s.telegram_bot_token), ("飞书", s.feishu_app_id), ("钉钉", s.dingtalk_client_id)):
        console.print(f"[dim]·[/] {name}：{'已配置' if configured else '未配置'}")
    return 0 if ok else 1


def skills_cmd(action: str, target: str | None) -> None:
    from answerlife import skills as registry

    if action == "list":
        for s in registry.discover().values():
            console.print(f"[bold]{s.title or s.name}[/] [dim]{s.name} · {'内置' if s.builtin else '已安装'}[/]\n  {s.description}")
        console.print(f"\n[dim]自己的 skill 放在 {registry.user_dir()}，或 answerlife skills install <目录或 git 地址>[/]")
    elif action == "install" and target:
        console.print("[yellow]第三方 skill 只作为说明文字使用，不会执行其中的代码。安装前请先读一遍它的 SKILL.md。[/]")
        s = registry.install(target)
        console.print(f"[green]已安装 {s.name}[/]：{s.description}")
    elif action == "remove" and target:
        console.print("已移除。" if registry.uninstall(target) else "用户目录里没有这个 skill（内置的可以在网页上停用）。")
    else:
        console.print("用法：answerlife skills [list | install <目录或 git 地址> | remove <名字>]")


def main() -> None:
    parser = argparse.ArgumentParser(prog="answerlife", description="答案之书 Agent")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("chat", help="只开终端对话")
    sv = sub.add_parser("serve", help="只开服务：网页 + 接口 + IM")
    sv.add_argument("--host")
    sv.add_argument("--port", type=int)
    sub.add_parser("setup", help="配置模型与 IM")
    pr = sub.add_parser("pair", help="生成 IM 配对码")
    pr.add_argument("channel")
    sub.add_parser("doctor", help="自检")
    sk = sub.add_parser("skills", help="管理 skill：list / install <目录或 git 地址> / remove <名字>")
    sk.add_argument("action", choices=["list", "install", "remove"], nargs="?", default="list")
    sk.add_argument("target", nargs="?")
    args = parser.parse_args()
    if args.cmd is None:
        chat(with_server=True)
    elif args.cmd == "chat":
        chat(with_server=False)
    elif args.cmd == "serve":
        from answerlife import server
        from answerlife.settings import get_settings
        settings = get_settings()
        host = args.host or settings.host
        port = args.port or settings.port
        url_host = f"[{host}]" if ":" in host else host
        console.print(f"答案之书 Agent 运行在 {_web_entry_url(f'http://{url_host}:{port}')}")
        server.serve(args.host, args.port, log_level="info")
    elif args.cmd == "setup":
        setup()
    elif args.cmd == "pair":
        pair(args.channel)
    elif args.cmd == "doctor":
        sys.exit(doctor())
    elif args.cmd == "skills":
        skills_cmd(args.action, args.target)


if __name__ == "__main__":
    main()
