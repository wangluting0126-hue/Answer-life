"""本地存储：一个 SQLite 文件。会话、消息、长期记忆、情绪打卡、答案页、配对与开关。

所有数据只在本机。长期记忆和实验记录要先取得同意（consent），用户随时可以看、删、全部清空。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, channel TEXT NOT NULL, title TEXT DEFAULT '',
  created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, conv_id TEXT NOT NULL, role TEXT NOT NULL,
  content TEXT NOT NULL, meta TEXT DEFAULT '{}', created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id, id);
CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, content TEXT NOT NULL,
  conv_id TEXT DEFAULT '', created_at REAL NOT NULL, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS moods (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, score INTEGER NOT NULL,
  words TEXT DEFAULT '', note TEXT DEFAULT '', conv_id TEXT DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS pages (
  id TEXT PRIMARY KEY, conv_id TEXT DEFAULT '', date TEXT NOT NULL, title TEXT NOT NULL,
  theme TEXT DEFAULT '', issue_key TEXT DEFAULT '', action TEXT DEFAULT '', criterion TEXT DEFAULT '',
  file TEXT NOT NULL, record_id TEXT DEFAULT '', nudged INTEGER DEFAULT 0, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS journal (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, kind TEXT NOT NULL, title TEXT DEFAULT '',
  content TEXT NOT NULL, conv_id TEXT DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS letters (
  id INTEGER PRIMARY KEY AUTOINCREMENT, written_on TEXT NOT NULL, deliver_on TEXT NOT NULL, title TEXT DEFAULT '',
  content TEXT NOT NULL, delivered INTEGER DEFAULT 0, conv_id TEXT DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

MEMORY_KINDS = ("person", "fact", "preference", "boundary", "goal")


class Store:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._db.commit()

    @contextmanager
    def tx(self):
        with self._lock:
            try:
                yield self._db
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise

    def _all(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    def _one(self, sql: str, args: tuple = ()) -> dict | None:
        rows = self._all(sql, args)
        return rows[0] if rows else None

    # ── kv ──
    def get(self, key: str, default=None):
        row = self._one("SELECT value FROM kv WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def set(self, key: str, value) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, json.dumps(value, ensure_ascii=False)))

    def delete_key(self, key: str) -> None:
        with self.tx() as db:
            db.execute("DELETE FROM kv WHERE key=?", (key,))

    # ── 同意 ──
    def consent(self) -> bool | None:
        """None：还没问过；True：同意保存长期记忆与实验记录；False：拒绝。"""
        return self.get("consent.memory")

    def set_consent(self, granted: bool) -> None:
        self.set("consent.memory", bool(granted))

    # ── 会话与消息 ──
    def new_conversation(self, channel: str, title: str = "") -> str:
        cid = uuid.uuid4().hex[:12]
        now = time.time()
        with self.tx() as db:
            db.execute("INSERT INTO conversations VALUES(?,?,?,?,?)", (cid, channel, title, now, now))
        return cid

    def conversation(self, cid: str) -> dict | None:
        return self._one("SELECT * FROM conversations WHERE id=?", (cid,))

    def conversations(self, limit: int = 50) -> list[dict]:
        return self._all("SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,))

    def delete_conversation(self, cid: str) -> None:
        with self.tx() as db:
            db.execute("DELETE FROM messages WHERE conv_id=?", (cid,))
            db.execute("DELETE FROM conversations WHERE id=?", (cid,))

    def add_message(self, cid: str, role: str, content: str, meta: dict | None = None) -> None:
        now = time.time()
        with self.tx() as db:
            db.execute("INSERT INTO messages(conv_id,role,content,meta,created_at) VALUES(?,?,?,?,?)",
                       (cid, role, content, json.dumps(meta or {}, ensure_ascii=False), now))
            db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, cid))
            if role == "user":
                db.execute("UPDATE conversations SET title=? WHERE id=? AND title=''", (content[:24], cid))

    def messages(self, cid: str, limit: int | None = None) -> list[dict]:
        rows = self._all("SELECT * FROM messages WHERE conv_id=? ORDER BY id DESC" + (" LIMIT ?" if limit else ""),
                         (cid, limit) if limit else (cid,))
        for r in rows:
            r["meta"] = json.loads(r["meta"] or "{}")
        return list(reversed(rows))

    def reflection_entries(self, start: str, end: str, after: float, before: float) -> list[dict]:
        notes = self._all(
            "SELECT date, substr(COALESCE(NULLIF(content,''), title), 1, 280) AS text, "
            "created_at, 'journal' AS kind FROM journal WHERE date BETWEEN ? AND ? "
            "ORDER BY date DESC, id DESC LIMIT 24", (start, end),
        )
        pages = self._all(
            "SELECT date, title AS text, created_at, 'page' AS kind FROM pages "
            "WHERE date BETWEEN ? AND ? ORDER BY date DESC, created_at DESC LIMIT 24", (start, end),
        )
        chats = self._all(
            "SELECT NULL AS date, substr(content, 1, 280) AS text, created_at, 'chat' AS kind "
            "FROM messages WHERE role='user' AND created_at>=? AND created_at<? "
            "ORDER BY created_at DESC, id DESC LIMIT 24", (after, before),
        )
        return notes + pages + chats

    # ── 长期记忆 ──
    def remember(self, kind: str, content: str, cid: str = "") -> int:
        if kind not in MEMORY_KINDS:
            kind = "fact"
        content = content.strip()
        existing = self._one("SELECT id FROM memories WHERE active=1 AND content=?", (content,))
        if existing:
            return existing["id"]
        with self.tx() as db:
            cur = db.execute("INSERT INTO memories(kind,content,conv_id,created_at) VALUES(?,?,?,?)",
                             (kind, content, cid, time.time()))
            return int(cur.lastrowid)

    def memories(self) -> list[dict]:
        return self._all("SELECT id,kind,content,created_at FROM memories WHERE active=1 ORDER BY id")

    def forget(self, memory_id: int) -> bool:
        with self.tx() as db:
            return db.execute("DELETE FROM memories WHERE id=?", (int(memory_id),)).rowcount > 0

    def forget_all(self) -> None:
        with self.tx() as db:
            for table in ("memories", "moods", "journal", "letters"):
                db.execute(f"DELETE FROM {table}")

    # ── 情绪打卡 ──
    def log_mood(self, date: str, score: int, words: str = "", note: str = "", cid: str = "") -> int:
        score = max(1, min(10, int(score)))
        with self.tx() as db:
            cur = db.execute("INSERT INTO moods(date,score,words,note,conv_id,created_at) VALUES(?,?,?,?,?,?)",
                             (date, score, words, note, cid, time.time()))
            return int(cur.lastrowid)

    def moods(self, start: str, end: str) -> list[dict]:
        return self._all("SELECT date,score,words,note FROM moods WHERE date BETWEEN ? AND ? ORDER BY date,id", (start, end))

    # ── 答案页 ──
    def add_page(self, page: dict) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO pages(id,conv_id,date,title,theme,issue_key,action,criterion,file,record_id,created_at)"
                       " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (page["id"], page.get("conv_id", ""), page["date"], page["title"], page.get("theme", ""),
                        page.get("issue_key", ""), page.get("action", ""), page.get("criterion", ""),
                        page["file"], page.get("record_id", ""), time.time()))

    def pages(self, limit: int = 100) -> list[dict]:
        return self._all("SELECT * FROM pages ORDER BY created_at DESC LIMIT ?", (limit,))

    def due_checkins(self, before_date: str) -> list[dict]:
        """七天实验到期、还没问过的页。"""
        return self._all("SELECT * FROM pages WHERE nudged=0 AND date<=? ORDER BY date", (before_date,))

    def mark_nudged(self, page_id: str) -> None:
        with self.tx() as db:
            db.execute("UPDATE pages SET nudged=1 WHERE id=?", (page_id,))

    # ── 日记（想法记录、三件小事等） ──
    def add_journal(self, date: str, kind: str, title: str, content: str, cid: str = "") -> int:
        with self.tx() as db:
            cur = db.execute("INSERT INTO journal(date,kind,title,content,conv_id,created_at) VALUES(?,?,?,?,?,?)",
                             (date, kind, title, content, cid, time.time()))
            return int(cur.lastrowid)

    def journal(self, limit: int = 50, kind: str = "") -> list[dict]:
        if kind:
            return self._all("SELECT * FROM journal WHERE kind=? ORDER BY created_at DESC LIMIT ?", (kind, limit))
        return self._all("SELECT * FROM journal ORDER BY created_at DESC LIMIT ?", (limit,))

    def delete_journal(self, jid: int) -> bool:
        with self.tx() as db:
            return db.execute("DELETE FROM journal WHERE id=?", (int(jid),)).rowcount > 0

    # ── 写给未来的信 ──
    def add_letter(self, written_on: str, deliver_on: str, title: str, content: str, cid: str = "") -> int:
        with self.tx() as db:
            cur = db.execute("INSERT INTO letters(written_on,deliver_on,title,content,conv_id,created_at) VALUES(?,?,?,?,?,?)",
                             (written_on, deliver_on, title, content, cid, time.time()))
            return int(cur.lastrowid)

    def letters(self, today: str) -> dict:
        """已到期的信可以读；没到期的只给日期和标题，像真正封好的信。"""
        arrived = self._all("SELECT * FROM letters WHERE deliver_on<=? ORDER BY deliver_on DESC", (today,))
        sealed = self._all("SELECT id,written_on,deliver_on,title FROM letters WHERE deliver_on>? ORDER BY deliver_on", (today,))
        return {"arrived": arrived, "sealed": sealed}

    def due_letters(self, today: str) -> list[dict]:
        return self._all("SELECT * FROM letters WHERE delivered=0 AND deliver_on<=? ORDER BY deliver_on", (today,))

    def mark_letter_delivered(self, lid: int) -> None:
        with self.tx() as db:
            db.execute("UPDATE letters SET delivered=1 WHERE id=?", (int(lid),))

    def delete_letter(self, lid: int) -> bool:
        with self.tx() as db:
            return db.execute("DELETE FROM letters WHERE id=?", (int(lid),)).rowcount > 0
