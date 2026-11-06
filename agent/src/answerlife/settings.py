"""配置：全部来自环境变量和数据目录下的 .env。数据目录默认 ~/.answerlife，可用 ANSWERLIFE_HOME 改。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PACKAGE = Path(__file__).resolve().parent
SKILL_DIR = PACKAGE / "skills" / "answer-book"


def home() -> Path:
    path = Path(os.environ.get("ANSWERLIFE_HOME", "~/.answerlife")).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _bool(key: str, default: bool) -> bool:
    value = _env(key)
    return default if not value else value.lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    home: Path
    provider: str = "anthropic"              # anthropic / openai / deepseek / mock
    fallback: str = ""                       # 主模型不可用时切换到哪一家，留空不启用
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "low"            # 聊天以低延迟为先；出页质量不够时调到 medium
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    max_tokens: int = 16000
    history_turns: int = 24                  # 每次带给模型的最近消息条数
    timezone: str = "Asia/Shanghai"
    host: str = "127.0.0.1"
    port: int = 8020
    public_url: str = ""                     # IM 里给出页面链接用；留空用本机地址
    telegram_bot_token: str = ""
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_api_base: str = "https://open.feishu.cn"
    dingtalk_client_id: str = ""
    dingtalk_client_secret: str = ""
    checkin_push: bool = True                # 七天实验到期时在 IM 里问一句
    extra: dict = field(default_factory=dict)

    @property
    def db_path(self) -> Path:
        return self.home / "answerlife.db"

    @property
    def pages_dir(self) -> Path:
        path = self.home / "pages"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def book_home(self) -> Path:
        """答案之书的实验记录目录（skill 原生格式，sessions/*.json）。"""
        return self.home / "book"

    @property
    def soul_path(self) -> Path:
        return self.home / "SOUL.md"

    @property
    def base_url(self) -> str:
        return (self.public_url or f"http://localhost:{self.port}").rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = home()
    load_dotenv(root / ".env", override=False)
    load_dotenv(Path.cwd() / ".env", override=False)
    return Settings(
        home=root,
        provider=_env("AI_PROVIDER", "anthropic").lower(),
        fallback=_env("AI_FALLBACK").lower(),
        anthropic_model=_env("ANTHROPIC_MODEL", "claude-opus-5-5"),
        anthropic_effort=_env("ANTHROPIC_EFFORT", "low"),
        openai_base_url=_env("OPENAI_BASE_URL"),
        openai_api_key=_env("OPENAI_API_KEY"),
        openai_model=_env("OPENAI_MODEL"),
        deepseek_api_key=_env("DEEPSEEK_API_KEY"),
        deepseek_model=_env("DEEPSEEK_MODEL", "deepseek-chat"),
        deepseek_base_url=_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        max_tokens=int(_env("MAX_TOKENS", "16000") or 16000),
        history_turns=int(_env("HISTORY_TURNS", "24") or 24),
        timezone=_env("TIMEZONE", "Asia/Shanghai"),
        host=_env("HOST", "127.0.0.1"),
        port=int(_env("PORT", "8020") or 8020),
        public_url=_env("PUBLIC_URL"),
        telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
        feishu_app_id=_env("FEISHU_APP_ID"),
        feishu_app_secret=_env("FEISHU_APP_SECRET"),
        feishu_api_base=_env("FEISHU_API_BASE", "https://open.feishu.cn"),
        dingtalk_client_id=_env("DINGTALK_CLIENT_ID"),
        dingtalk_client_secret=_env("DINGTALK_CLIENT_SECRET"),
        checkin_push=_bool("CHECKIN_PUSH", True),
    )


def reload() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def today() -> str:
    import datetime as dt
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(get_settings().timezone)
    except Exception:  # noqa: BLE001
        tz = None
    return dt.datetime.now(tz).date().isoformat()
