from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from openevo.config.settings import OpenEvoConfig, get_settings

_ALLOWED = frozenset({"entities", "concepts", "comparisons", "queries"})
_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


def _slugify(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", name.lower().strip(), flags=re.UNICODE)
    return re.sub(r"-+", "-", s).strip("-") or "untitled"


class WikiStore:
    """Structured markdown wiki + SQLite index for query."""

    def __init__(self, root: Path | None = None, cfg: OpenEvoConfig | None = None) -> None:
        self._cfg = cfg or get_settings()
        nc = self._cfg.notes
        self.root = Path(
            os.path.expandvars(os.path.expanduser(root or nc.path))
        ).resolve()
        self.meta = self.root / ".openevo"
        self._db_path = self.meta / "wiki_index.sqlite3"
        self._lock = threading.RLock()
        self._init_layout()
        self._init_db()

    def exists(self) -> bool:
        return self.root.exists() and (self.root / "SCHEMA.md").exists()

    def _init_layout(self) -> None:
        for d in [
            self.root,
            self.meta,
            self.root / "entities",
            self.root / "concepts",
            self.root / "comparisons",
            self.root / "queries",
            self.root / "raw" / "articles",
        ]:
            d.mkdir(parents=True, exist_ok=True)
        schema = self.root / "SCHEMA.md"
        if not schema.exists():
            schema.write_text(
                "# OpenEvo Wiki Schema\n\n- YAML frontmatter\n- [[wikilinks]]\n",
                encoding="utf-8",
            )
        idx = self.root / "index.md"
        if not idx.exists():
            idx.write_text("# Index\n\n", encoding="utf-8")
        log = self.root / "log.md"
        if not log.exists():
            log.write_text("# Log\n\n", encoding="utf-8")

    def _init_db(self) -> None:
        with self._lock:
            self.meta.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pages (
                        relpath TEXT PRIMARY KEY,
                        section TEXT NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._db_path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def get_stats(self) -> dict[str, Any]:
        n = 0
        for sec in _ALLOWED:
            n += len(list((self.root / sec).glob("*.md")))
        return {"root": str(self.root), "total_pages": n}

    def read_schema(self) -> str:
        return (self.root / "SCHEMA.md").read_text(encoding="utf-8")

    def read_index(self) -> str:
        return (self.root / "index.md").read_text(encoding="utf-8")

    def read_log_tail(self, n: int = 30) -> str:
        text = (self.root / "log.md").read_text(encoding="utf-8")
        return "\n".join(text.splitlines()[-max(1, n) :])

    def get_orient_payload(self, log_entries: int = 30) -> dict[str, Any]:
        return {
            "schema": self.read_schema() if self.exists() else "",
            "index": self.read_index() if (self.root / "index.md").exists() else "",
            "recent_log": self.read_log_tail(log_entries),
            "stats": self.get_stats(),
        }

    def _extract_links(self, text: str) -> list[str]:
        out: list[str] = []
        for m in _WIKILINK.findall(text):
            out.append(_slugify(m.split("|", 1)[0].split("#", 1)[0]))
        return sorted(set(out))

    def write_page(
        self,
        section: str,
        title: str,
        body: str,
        *,
        tags: list[str] | None = None,
    ) -> Path:
        sec = section if section in _ALLOWED else "concepts"
        slug = _slugify(title)
        path = (self.root / sec / f"{slug}.md").resolve()
        path.relative_to(self.root)
        now = time.strftime("%Y-%m-%d")
        tags = tags or ["note"]
        fm = (
            "---\n"
            f"title: {title}\n"
            f"updated: {now}\n"
            f"tags: {json.dumps(tags, ensure_ascii=False)}\n"
            "---\n\n"
        )
        content = fm + body.strip() + "\n"
        path.write_text(content, encoding="utf-8")
        rel = str(path.relative_to(self.root))
        ts = int(time.time())
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    """
                    INSERT INTO pages(relpath, section, title, content, updated_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(relpath) DO UPDATE SET
                        section=excluded.section,
                        title=excluded.title,
                        content=excluded.content,
                        updated_at=excluded.updated_at
                    """,
                    (rel, sec, title, content, ts),
                )
                conn.commit()
            finally:
                conn.close()
        self._append_log("write", title, [rel])
        self._rebuild_index_md()
        return path

    def _append_log(self, action: str, subject: str, details: list[str]) -> None:
        ts = time.strftime("%Y-%m-%d")
        lines = f"\n## [{ts}] {action} | {subject}\n" + "\n".join(f"- {d}" for d in details) + "\n"
        with (self.root / "log.md").open("a", encoding="utf-8") as f:
            f.write(lines)

    def _rebuild_index_md(self) -> None:
        lines = ["# Index", ""]
        for sec in _ALLOWED:
            lines.append(f"## {sec.title()}")
            for p in sorted((self.root / sec).glob("*.md")):
                lines.append(f"- [[{p.stem}]]")
            lines.append("")
        (self.root / "index.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    def query(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        q = (query or "").strip().lower()
        tokens = [t for t in re.split(r"\s+", q) if t]
        lim = max(1, min(limit, 100))
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute("SELECT * FROM pages").fetchall()
            finally:
                conn.close()
        scored: list[tuple[float, dict[str, Any]]] = []
        for r in rows:
            text = (r["content"] or "").lower()
            tit = (r["title"] or "").lower()
            score = sum(1 for t in tokens if t in text or t in tit)
            if q and score == 0 and q not in text:
                continue
            base = score + (0.5 if q and q in tit else 0)
            scored.append(
                (
                    base + r["updated_at"] / 1e12,
                    {
                        "path": r["relpath"],
                        "title": r["title"],
                        "snippet": (r["content"] or "")[:240].replace("\n", " "),
                        "rank": -base,
                    },
                )
            )
        scored.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in scored[:lim]]

    def ingest_text(self, title: str, text: str, *, section: str = "concepts") -> Path:
        raw = self.root / "raw" / "articles" / f"{_slugify(title)}.md"
        raw.write_text(text, encoding="utf-8")
        return self.write_page(section, title, text[:8000], tags=["ingested"])
