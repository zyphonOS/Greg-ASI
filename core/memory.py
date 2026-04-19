from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.utils import data_path, ensure_directory, read_json, write_json


class JsonMemory:
    def __init__(self, memory_path: str | Path | None = None):
        self.memory_path = Path(memory_path) if memory_path else data_path("memory.json")

    def save_memory(self, key: str, value: Any) -> None:
        payload = read_json(self.memory_path, {})
        payload[key] = value
        write_json(self.memory_path, payload)

    def load_memory(self, key: str, default: Any = None) -> Any:
        payload = read_json(self.memory_path, {})
        return payload.get(key, default)

    def all_memory(self) -> dict[str, Any]:
        return read_json(self.memory_path, {})


class SQLiteMemory:
    def __init__(
        self,
        db_path: str | Path | None = None,
        watch_dir: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path else data_path("greg_memory.db")
        self.watch_dir = Path(watch_dir) if watch_dir else data_path("memory_store")
        ensure_directory(self.db_path.parent)
        ensure_directory(self.watch_dir)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._seen_files: dict[str, float] = {}
        self._fts_enabled = False
        self._init_db()
        self.scan_watch_dir()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    content TEXT,
                    metadata TEXT,
                    timestamp TEXT
                )
                """
            )
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source)")
            try:
                self.conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                    USING fts5(content, source UNINDEXED, metadata UNINDEXED, timestamp UNINDEXED)
                    """
                )
                self._fts_enabled = True
            except sqlite3.OperationalError:
                self._fts_enabled = False

    def _normalise_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, (dict, list, tuple)):
            return json.dumps(content, ensure_ascii=True, sort_keys=True)
        return str(content).strip()

    def add(
        self,
        source: str,
        content: Any,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        text = self._normalise_content(content)
        if not text:
            return
        ts = datetime.now(timezone.utc).isoformat()
        metadata_payload = metadata or {}
        metadata_json = json.dumps(metadata_payload, ensure_ascii=True)
        with self._lock, self.conn:
            cursor = self.conn.execute(
                "INSERT INTO memories (source, content, metadata, timestamp) VALUES (?, ?, ?, ?)",
                (source, text, metadata_json, ts),
            )
            if self._fts_enabled:
                self.conn.execute(
                    "INSERT INTO memories_fts (rowid, content, source, metadata, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (cursor.lastrowid, text, source, metadata_json, ts),
                )

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        self.scan_watch_dir()
        term = (query or "").strip()
        if not term:
            return []
        with self._lock:
            rows = []
            if self._fts_enabled:
                try:
                    rows = self.conn.execute(
                        """
                        SELECT m.source, m.content, m.metadata, m.timestamp
                        FROM memories m
                        JOIN memories_fts f ON m.id = f.rowid
                        WHERE memories_fts MATCH ?
                        ORDER BY m.timestamp DESC
                        LIMIT ?
                        """,
                        (term, limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            if not rows:
                rows = self.conn.execute(
                    """
                    SELECT source, content, metadata, timestamp
                    FROM memories
                    WHERE content LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (f"%{term}%", limit),
                ).fetchall()
        return [
            {
                "source": row["source"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"] or "{}"),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def recall(self, query: str, limit: int = 10) -> str:
        results = self.search(query, limit=limit)
        if not results:
            return "No relevant memories found."
        return "\n".join(
            f"[{item['timestamp']}] [{item['source']}] {item['content']}"
            for item in results
        )

    def latest_by_source(self, source: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT source, content, metadata, timestamp
                FROM memories
                WHERE source = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (source, limit),
            ).fetchall()
        return [
            {
                "source": row["source"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"] or "{}"),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def records_by_prefix(self, source_prefix: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT source, content, metadata, timestamp
                FROM memories
                WHERE source LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (f"{source_prefix}%", limit),
            ).fetchall()
        return [
            {
                "source": row["source"],
                "content": row["content"],
                "metadata": json.loads(row["metadata"] or "{}"),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def scan_watch_dir(self) -> int:
        imported = 0
        for path in self.watch_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            key = str(path.resolve())
            if self._seen_files.get(key) == mtime:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            self.add(
                "watch_dir",
                content,
                {
                    "path": key,
                    "name": path.name,
                    "suffix": path.suffix,
                    "watched": True,
                },
            )
            self._seen_files[key] = mtime
            imported += 1
        return imported

    def log_cli(self, command: str, payload: dict[str, Any] | None = None) -> None:
        self.add("cli", command, payload or {})

    def log_browser_event(self, source: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        self.add(source, content, metadata or {})


class ConversationStateStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else data_path("greg_state.db")
        ensure_directory(self.db_path.parent)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS state (
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                expires_at REAL,
                updated_at REAL,
                PRIMARY KEY (user_id, key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                intent TEXT,
                metadata TEXT,
                ts REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_messages_user_ts
            ON conversation_messages (user_id, ts)
            """
        )
        return conn

    def save_state(self, user_id: str, key: str, value: Any, ttl: float | None = None) -> None:
        if not user_id or not key:
            return
        expires_at = time.time() + ttl if ttl else None
        payload = json.dumps(value)
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO state (user_id, key, value, expires_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, key, payload, expires_at, time.time()),
            )

    def load_state(self, user_id: str, key: str):
        if not user_id or not key:
            return None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM state WHERE user_id = ? AND key = ?",
                (user_id, key),
            ).fetchone()
        if not row:
            return None
        value, expires_at = row
        if expires_at and expires_at < time.time():
            with self._conn() as conn:
                conn.execute("DELETE FROM state WHERE user_id = ? AND key = ?", (user_id, key))
            return None
        try:
            return json.loads(value) if value else None
        except Exception:
            return None

    def save_conversation_turn(
        self,
        user_id: str,
        role: str,
        text: str,
        intent: str | None = None,
        metadata: dict[str, Any] | None = None,
        max_messages: int = 200,
    ) -> None:
        if not user_id or not role or not text:
            return
        payload = json.dumps(metadata or {})
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO conversation_messages (user_id, role, text, intent, metadata, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, role, text, intent, payload, time.time()),
            )
            conn.execute(
                """
                DELETE FROM conversation_messages
                WHERE user_id = ?
                  AND id NOT IN (
                      SELECT id
                      FROM conversation_messages
                      WHERE user_id = ?
                      ORDER BY id DESC
                      LIMIT ?
                  )
                """,
                (user_id, user_id, max_messages),
            )

    def load_conversation_history(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        if not user_id or limit <= 0:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT role, text, intent, metadata, ts
                FROM conversation_messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        history = []
        for role, text, intent, metadata, ts in reversed(rows):
            try:
                meta = json.loads(metadata) if metadata else {}
            except Exception:
                meta = {}
            history.append(
                {
                    "role": role,
                    "content": text,
                    "text": text,
                    "intent": intent,
                    "metadata": meta,
                    "ts": ts,
                }
            )
        return history


_sqlite_memory: SQLiteMemory | None = None


def get_sqlite_memory() -> SQLiteMemory:
    global _sqlite_memory
    if _sqlite_memory is None:
        _sqlite_memory = SQLiteMemory()
    return _sqlite_memory
