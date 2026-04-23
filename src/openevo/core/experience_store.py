"""SQLite persistence for experiences and graph edges."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openevo.core.experience_models import Experience, ExperienceID, Relation


def _dt_to_ts(dt: datetime) -> float:
    return dt.timestamp()


def _ts_to_dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


class ExperienceSQLiteStore:
    """Stores experience vectors/metadata and relation edges."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiences (
                    id TEXT PRIMARY KEY,
                    vector TEXT NOT NULL,
                    modality TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    source_agent TEXT NOT NULL,
                    content_summary TEXT NOT NULL,
                    content_payload TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS exp_edges (
                    from_id TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    PRIMARY KEY (from_id, to_id, relation)
                );
                CREATE INDEX IF NOT EXISTS idx_exp_domain ON experiences(domain);
                CREATE INDEX IF NOT EXISTS idx_exp_agent ON experiences(source_agent);
                CREATE INDEX IF NOT EXISTS idx_edge_from ON exp_edges(from_id);
                CREATE INDEX IF NOT EXISTS idx_edge_to ON exp_edges(to_id);
                """
            )

    def upsert_experience(self, exp: Experience) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO experiences
                (id, vector, modality, domain, source_agent, content_summary,
                 content_payload, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exp.id,
                    json.dumps(exp.vector),
                    exp.modality,
                    exp.domain,
                    exp.source_agent,
                    exp.content_summary,
                    json.dumps(exp.content_payload),
                    json.dumps(exp.metadata),
                    _dt_to_ts(exp.timestamp),
                ),
            )

    def get_experience(self, exp_id: ExperienceID) -> Experience | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM experiences WHERE id = ?", (exp_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_exp(row)

    def _row_to_exp(self, row: tuple[Any, ...]) -> Experience:
        (
            eid,
            vector_json,
            modality,
            domain,
            source_agent,
            summary,
            payload_json,
            meta_json,
            created_at,
        ) = row
        return Experience(
            id=eid,
            vector=json.loads(vector_json),
            modality=modality,
            domain=domain,
            timestamp=_ts_to_dt(created_at),
            source_agent=source_agent,
            content_summary=summary,
            content_payload=json.loads(payload_json),
            metadata=json.loads(meta_json),
        )

    def iter_experiences(self) -> list[Experience]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM experiences").fetchall()
        return [self._row_to_exp(r) for r in rows]

    def add_edge(
        self,
        from_id: ExperienceID,
        to_id: ExperienceID,
        relation: Relation,
        confidence: float,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO exp_edges (from_id, to_id, relation, confidence)
                VALUES (?, ?, ?, ?)
                """,
                (from_id, to_id, relation.value, confidence),
            )

    def out_edges(self, from_id: ExperienceID) -> list[tuple[str, Relation, float]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT to_id, relation, confidence FROM exp_edges WHERE from_id = ?",
                (from_id,),
            ).fetchall()
        return [(r[0], Relation(r[1]), r[2]) for r in rows]

    def in_edges(self, to_id: ExperienceID) -> list[tuple[str, Relation, float]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT from_id, relation, confidence FROM exp_edges WHERE to_id = ?",
                (to_id,),
            ).fetchall()
        return [(r[0], Relation(r[1]), r[2]) for r in rows]


def new_experience_id() -> str:
    return str(uuid.uuid4())
