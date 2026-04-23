from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from openevo.config.settings import OpenEvoConfig, get_settings

ENTRY_DELIMITER = "\n§\n"

_THREAT_PATTERNS = [
    (r"ignore\s+(previous|all|above|prior)\s+instructions", "prompt_injection"),
    (r"you\s+are\s+now\s+", "role_hijack"),
    (r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)", "disregard_rules"),
]


def _scan_threat(content: str) -> str | None:
    for pattern, pid in _THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return f"Blocked: threat pattern '{pid}'."
    return None


def _entry_key(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:16]


class MemoryService:
    """Curated dual-bucket memory (memory/user) + episodic store for plugins — SQLite."""

    def __init__(self, data_dir: Path | None = None, cfg: OpenEvoConfig | None = None) -> None:
        self._cfg = cfg or get_settings()
        self._root = data_dir or self._cfg.resolve_data_dir()
        self._root.mkdir(parents=True, exist_ok=True)
        self._db = self._root / "memory.sqlite3"
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
        except sqlite3.Error:
            pass
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS curated (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target TEXT NOT NULL CHECK(target IN ('memory','user')),
                        content TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        score REAL NOT NULL,
                        source TEXT DEFAULT 'tool',
                        created_at INTEGER NOT NULL,
                        last_used_at INTEGER NOT NULL,
                        UNIQUE(target, content_hash)
                    );
                    CREATE TABLE IF NOT EXISTS episodic (
                        id TEXT PRIMARY KEY,
                        group_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        ts INTEGER NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_epi_group ON episodic(group_id);
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def _char_count(self, conn: sqlite3.Connection, target: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(SUM(LENGTH(content)), 0) FROM curated WHERE target = ?",
            (target,),
        ).fetchone()
        return int(row[0] or 0)

    def _limit(self, target: str) -> int:
        m = self._cfg.memory
        return m.user_char_limit if target == "user" else m.memory_char_limit

    def _evict(self, conn: sqlite3.Connection, target: str, need: int, preserve_hash: str) -> int:
        if not self._cfg.memory.governance_enabled:
            return 0
        limit = self._limit(target)
        while self._char_count(conn, target) + need > limit:
            row = conn.execute(
                """
                SELECT content_hash FROM curated
                WHERE target = ? AND content_hash != ?
                ORDER BY score ASC, last_used_at ASC LIMIT 1
                """,
                (target, preserve_hash),
            ).fetchone()
            if not row:
                break
            conn.execute("DELETE FROM curated WHERE target = ? AND content_hash = ?", (target, row[0]))
        return 0

    def add(self, target: str, content: str, *, source: str = "tool", score: float = 0.5) -> dict[str, Any]:
        content = (content or "").strip()
        if not content:
            return {"success": False, "error": "Content empty"}
        err = _scan_threat(content)
        if err:
            return {"success": False, "error": err}
        if target not in {"memory", "user"}:
            return {"success": False, "error": "Invalid target"}
        h = _entry_key(content)
        mcfg = self._cfg.memory
        s = max(mcfg.score_min, min(float(score), mcfg.score_max))
        now = int(time.time())
        with self._lock:
            conn = self._connect()
            try:
                ex = conn.execute(
                    "SELECT 1 FROM curated WHERE target = ? AND content_hash = ?",
                    (target, h),
                ).fetchone()
                if ex:
                    conn.execute(
                        "UPDATE curated SET last_used_at = ? WHERE target = ? AND content_hash = ?",
                        (now, target, h),
                    )
                    conn.commit()
                    return {"success": True, "message": "Already exists (updated last_used_at)", "target": target}

                need = len(content)
                self._evict(conn, target, need, h)
                if self._char_count(conn, target) + need > self._limit(target):
                    return {
                        "success": False,
                        "error": f"Would exceed char limit for {target}",
                        "usage": self._char_count(conn, target),
                    }
                conn.execute(
                    """
                    INSERT INTO curated(target, content, content_hash, score, source, created_at, last_used_at)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (target, content, h, s, source, now, now),
                )
                conn.commit()
                return {"success": True, "target": target, "message": "Added"}
            finally:
                conn.close()

    def remove(self, target: str, old_text: str) -> dict[str, Any]:
        old_text = (old_text or "").strip()
        if not old_text:
            return {"success": False, "error": "old_text empty"}
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, content FROM curated WHERE target = ? AND INSTR(content, ?) > 0",
                    (target, old_text),
                ).fetchall()
                if not rows:
                    return {"success": False, "error": "No match"}
                if len(rows) > 1:
                    return {"success": False, "error": "Multiple matches; be specific"}
                conn.execute("DELETE FROM curated WHERE id = ?", (rows[0][0],))
                conn.commit()
                return {"success": True, "message": "Removed"}
            finally:
                conn.close()

    def replace(self, target: str, old_text: str, new_content: str, *, source: str = "tool", score: float = 0.5) -> dict[str, Any]:
        r = self.remove(target, old_text)
        if not r.get("success"):
            return r
        return self.add(target, new_content, source=source, score=score)

    def _list_curated(self, target: str) -> list[str]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT content FROM curated WHERE target = ? ORDER BY last_used_at DESC",
                    (target,),
                ).fetchall()
                return [r[0] for r in rows]
            finally:
                conn.close()

    def render_prompt_blocks(self) -> tuple[str | None, str | None]:
        def block(target: str, label: str) -> str | None:
            entries = self._list_curated(target)
            if not entries:
                return None
            body = ENTRY_DELIMITER.join(entries)
            cur = len(body)
            lim = self._limit(target)
            pct = int((cur / lim) * 100) if lim else 0
            sep = "═" * 46
            return f"{sep}\n{label} [{pct}% — {cur:,}/{lim:,} chars]\n{sep}\n{body}"

        mem = block("memory", "MEMORY (workflow notes)")
        usr = block("user", "USER PROFILE")
        return mem, usr

    def append_episodic(
        self, group_id: str, user_id: str, messages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        now = int(time.time() * 1000)
        with self._lock:
            conn = self._connect()
            try:
                n = 0
                for m in messages:
                    conn.execute(
                        """
                        INSERT INTO episodic(id, group_id, user_id, role, content, ts)
                        VALUES(?,?,?,?,?,?)
                        """,
                        (
                            str(uuid.uuid4()),
                            group_id,
                            user_id,
                            str(m.get("role") or "user"),
                            str(m.get("content") or ""),
                            int(m.get("timestamp") or now),
                        ),
                    )
                    n += 1
                conn.commit()
                return {"status": "ok", "count": n, "request_id": str(uuid.uuid4())}
            finally:
                conn.close()

    def search_episodic(self, query: str, group_id: str | None, top_k: int = 5) -> list[dict[str, Any]]:
        q = (query or "").strip().lower()
        tokens = [t for t in re.split(r"\s+", q) if len(t) > 1]
        with self._lock:
            conn = self._connect()
            try:
                sql = "SELECT * FROM episodic WHERE 1=1"
                args: list[Any] = []
                if group_id:
                    sql += " AND group_id = ?"
                    args.append(group_id)
                rows = conn.execute(sql, args).fetchall()
                scored: list[tuple[float, sqlite3.Row]] = []
                for r in rows:
                    text = (r["content"] or "").lower()
                    if not q:
                        scored.append((float(r["ts"]), r))
                        continue
                    score = sum(1 for t in tokens if t in text) + (2 if q in text else 0)
                    if score > 0 or q in text:
                        scored.append((float(score) + r["ts"] / 1e15, r))
                scored.sort(key=lambda x: x[0], reverse=True)
                out: list[dict[str, Any]] = []
                for _, r in scored[:top_k]:
                    d = dict(r)
                    d["score"] = round(min(0.99, 0.55 + 0.05 * len(tokens)), 2)
                    out.append(d)
                return out
            finally:
                conn.close()

    def get_episodic(self, group_id: str | None, page: int, page_size: int) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                sql = "SELECT * FROM episodic WHERE 1=1"
                args: list[Any] = []
                if group_id:
                    sql += " AND group_id = ?"
                    args.append(group_id)
                total = conn.execute(
                    f"SELECT COUNT(*) FROM episodic WHERE 1=1"
                    + (" AND group_id = ?" if group_id else ""),
                    (group_id,) if group_id else (),
                ).fetchone()[0]
                sql += " ORDER BY ts DESC LIMIT ? OFFSET ?"
                args.extend([page_size, (page - 1) * page_size])
                rows = conn.execute(sql, args).fetchall()
                return {
                    "episodes": [dict(r) for r in rows],
                    "total_count": total,
                    "count": len(rows),
                }
            finally:
                conn.close()
