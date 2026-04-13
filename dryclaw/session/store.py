from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4


SESSIONS_DIR = Path.home() / ".dryclaw" / "sessions"
SESSIONS_DB = SESSIONS_DIR / "sessions.db"


@dataclass
class SessionSummary:
    id: str
    created_at: str
    snippet: str


def _messages_to_text(messages: list[dict]) -> str:
    chunks: list[str] = []
    for msg in messages:
        content = msg.get("content", "")
        chunks.append(str(content))
    return "\n".join(chunks)


class SessionStore:
    def __init__(self) -> None:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = SESSIONS_DB
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    content TEXT NOT NULL
                )
                """
            )
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts
                    USING fts5(id, title, created_at, content)
                    """
                )
            except sqlite3.OperationalError:
                # 兼容不支持 FTS5 的 sqlite 构建。
                pass

    def save(self, cwd: str, messages: list[dict]) -> Path:
        session_id = uuid4().hex[:8]
        created_at = datetime.now().isoformat(timespec="seconds")
        payload = {
            "id": session_id,
            "created_at": created_at,
            "cwd": cwd,
            "messages": messages,
            "reserved": {"fts_keywords": [], "summary": ""},
        }
        output = SESSIONS_DIR / f"{session_id}.json"
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        text = _messages_to_text(messages)
        title = self._build_title(messages)
        self._upsert_index(session_id=session_id, title=title, created_at=created_at, content=text)
        return output

    @staticmethod
    def _build_title(messages: list[dict]) -> str:
        for msg in messages:
            if msg.get("role") == "user":
                content = str(msg.get("content", "")).strip()
                if content:
                    return content[:80]
        return "untitled-session"

    def _upsert_index(self, session_id: str, title: str, created_at: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(id, title, created_at, content)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  title=excluded.title,
                  created_at=excluded.created_at,
                  content=excluded.content
                """,
                (session_id, title, created_at, content),
            )
            try:
                conn.execute("DELETE FROM sessions_fts WHERE id = ?", (session_id,))
                conn.execute(
                    "INSERT INTO sessions_fts(id, title, created_at, content) VALUES(?, ?, ?, ?)",
                    (session_id, title, created_at, content),
                )
            except sqlite3.OperationalError:
                # FTS5 不可用时优雅降级。
                pass

    def search(self, query: str, limit: int = 5) -> list[SessionSummary]:
        q = query.strip()
        if not q:
            return []

        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT id, created_at, snippet(sessions_fts, 3, '[', ']', '...', 16) AS snippet
                    FROM sessions_fts
                    WHERE sessions_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (q, max(1, min(50, limit))),
                ).fetchall()
            except sqlite3.OperationalError:
                return []

        return [
            SessionSummary(id=str(row["id"]), created_at=str(row["created_at"]), snippet=str(row["snippet"]))
            for row in rows
        ]


def save_session(cwd: str, messages: list[dict]) -> Path:
    return SessionStore().save(cwd=cwd, messages=messages)
