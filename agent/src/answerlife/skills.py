"""Skill 生态：每个能力是一个目录，入口是 SKILL.md（YAML frontmatter 写 name / description）。

设计参考 OpenClaw 与 Agent Skills 规范：
- 系统提示词里只放一份紧凑的 skill 索引（名字 + 一句话描述），不塞全文；
- 模型需要时调 use_skill 读全文，之后该 skill 在这段对话里保持"已激活"，全文进入可缓存的提示词段；
- 来源有两处：内置（随包）与用户目录 ~/.answerlife/skills；同名时用户目录优先，方便改写内置 skill；
- 第三方 skill 一律只当"说明书"用：不执行其中任何代码。工具只来自本包内置的 skill_tools。
- 界面用的字段（中文名、图标、颜色、开场白）放在可选的 meta.json，不改动 SKILL.md，保证 skill 仍能装进其他客户端。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from answerlife.settings import PACKAGE, home

BUILTIN_DIR = PACKAGE / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    builtin: bool
    title: str = ""
    icon: str = "spark"
    color: str = "#c0765a"
    starter: str = ""
    tagline: str = ""
    order: int = 50
    extra: dict = field(default_factory=dict)

    @property
    def body(self) -> str:
        return _split(self.path.joinpath("SKILL.md").read_text(encoding="utf-8"))[1].strip()

    def files(self) -> list[str]:
        """skill 目录里可供模型按需读取的参考文件（相对路径）。"""
        out = []
        for p in sorted(self.path.rglob("*")):
            if p.is_file() and p.suffix in (".md", ".txt", ".json", ".jsonl", ".yaml") and p.name not in ("SKILL.md", "meta.json"):
                rel = p.relative_to(self.path).as_posix()
                if not rel.startswith(("examples/", "quotes/", "demo/")):
                    out.append(rel)
        return out

    def read(self, rel: str) -> str:
        target = (self.path / rel).resolve()
        if self.path.resolve() not in target.parents or not target.is_file():
            raise ValueError("文件不在这个 skill 目录里")
        return target.read_text(encoding="utf-8")[:20000]

    def card(self, enabled: bool) -> dict:
        return {"name": self.name, "title": self.title or self.name, "description": self.description,
                "tagline": self.tagline, "icon": self.icon, "color": self.color, "starter": self.starter,
                "builtin": self.builtin, "enabled": enabled, "has_tools": self.name in TOOL_SKILLS}


# 带程序化工具的内置 skill（工具实现见 skill_tools/）
TOOL_SKILLS = {"answer-book", "calm-breath", "future-letter"}


def _split(text: str) -> tuple[dict, str]:
    """极简 YAML frontmatter 解析：只认顶层 key: value（够 SKILL.md 用，不引入 yaml 依赖）。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m[1].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("'\"")
    return meta, m[2]


def _load(path: Path, builtin: bool) -> Skill | None:
    entry = path / "SKILL.md"
    if not entry.is_file():
        return None
    meta, _ = _split(entry.read_text(encoding="utf-8"))
    name, desc = meta.get("name", ""), meta.get("description", "")
    if not NAME_RE.match(name) or not desc:
        return None
    ui = {}
    if (path / "meta.json").is_file():
        try:
            ui = json.loads((path / "meta.json").read_text(encoding="utf-8"))
        except ValueError:
            ui = {}
    known = {k: ui[k] for k in ("title", "icon", "color", "starter", "tagline", "order") if k in ui}
    return Skill(name=name, description=desc, path=path, builtin=builtin, **known)


def user_dir() -> Path:
    path = home() / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def discover() -> dict[str, Skill]:
    found: dict[str, Skill] = {}
    for base, builtin in ((BUILTIN_DIR, True), (user_dir(), False)):
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            skill = _load(d, builtin)
            if skill:
                found[skill.name] = skill          # 用户目录后读，同名覆盖内置
    return dict(sorted(found.items(), key=lambda kv: (kv[1].order, kv[0])))


def enabled(store) -> dict[str, Skill]:
    off = set(store.get("skills.disabled") or [])
    return {k: v for k, v in discover().items() if k not in off}


def set_enabled(store, name: str, on: bool) -> None:
    off = set(store.get("skills.disabled") or [])
    off.discard(name) if on else off.add(name)
    store.set("skills.disabled", sorted(off))


def index_text(skills: dict[str, Skill]) -> str:
    lines = [f"- {s.name}（{s.title or s.name}）：{s.description}" for s in skills.values()]
    return "\n".join(lines)


def active(store, conv_id: str) -> list[str]:
    return store.get(f"conv:{conv_id}:skills") or []


def activate(store, conv_id: str, name: str) -> None:
    names = active(store, conv_id)
    if name not in names:
        store.set(f"conv:{conv_id}:skills", [*names, name][-3:])   # 一段对话最多同时激活 3 个


def install(source: str) -> Skill:
    """从本地目录或 git 地址安装一个 skill 到用户目录。只复制文件，不执行任何东西。"""
    with tempfile.TemporaryDirectory() as tmp:
        if re.match(r"^(https?://|git@)", source):
            subprocess.run(["git", "clone", "--depth", "1", source, tmp + "/repo"], check=True, capture_output=True)
            root = Path(tmp) / "repo"
        else:
            root = Path(source).expanduser().resolve()
        candidates = [root] if (root / "SKILL.md").is_file() else [p.parent for p in root.glob("*/SKILL.md")]
        if len(candidates) != 1:
            raise ValueError(f"在 {source} 里找到 {len(candidates)} 个 SKILL.md，需要正好一个（可指向具体子目录）")
        skill = _load(candidates[0], builtin=False)
        if skill is None:
            raise ValueError("SKILL.md 的 frontmatter 需要 name（小写字母数字连字符）和 description")
        dest = user_dir() / skill.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(candidates[0], dest, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
                        symlinks=False)
    return _load(dest, builtin=False)  # type: ignore[return-value]


def uninstall(name: str) -> bool:
    dest = user_dir() / name
    if NAME_RE.match(name) and dest.is_dir():
        shutil.rmtree(dest)
        return True
    return False
