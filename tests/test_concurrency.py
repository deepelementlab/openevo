from __future__ import annotations

import concurrent.futures
import os
import sqlite3
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["OPENEVO_DATA_DIR"] = ""


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENEVO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OPENEVO_NOTES__PATH", str(tmp_path / "wiki"))
    from openevo.config.settings import clear_settings_cache

    clear_settings_cache()
    from openevo.api.server import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


def test_concurrent_memory_writes(client: TestClient) -> None:
    """Concurrent episodic writes via API (SQLite WAL)."""
    group_id = "concurrent-test"
    n_threads = 10
    n_messages_per_thread = 20

    def writer(thread_id: int) -> int:
        msgs = [
            {"role": "user", "content": f"msg-{thread_id}-{i}"} for i in range(n_messages_per_thread)
        ]
        r = client.post(
            "/api/v1/memories/group",
            json={"group_id": group_id, "user_id": "u1", "messages": msgs},
        )
        return r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as ex:
        futures = [ex.submit(writer, i) for i in range(n_threads)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert all(r == 200 for r in results)

    r = client.post(
        "/api/v1/memories/get",
        json={"filters": {"group_id": group_id}, "page": 1, "page_size": 2000},
    )
    assert r.status_code == 200
    assert r.json()["data"]["count"] == n_threads * n_messages_per_thread


def test_concurrent_curated_memory(client: TestClient) -> None:
    """Concurrent curated adds + snapshot reads."""
    n_threads = 5
    errors: list[Exception] = []

    def worker(thread_id: int) -> None:
        try:
            r = client.post(
                "/api/v1/memories/curated",
                json={
                    "action": "add",
                    "target": "memory",
                    "content": f"unique-thread-{thread_id}-{time.time_ns()} content",
                    "score": 0.7,
                },
            )
            assert r.status_code == 200
            assert r.json().get("success") is True
            time.sleep(0.01)
            r2 = client.get("/api/v1/prompt/snapshot")
            assert r2.status_code == 200
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors


def test_sqlite_wal_mode(client: TestClient) -> None:
    """Verify memory DB uses WAL journal mode."""
    client.post(
        "/api/v1/memories/group",
        json={"group_id": "wal-check", "user_id": "u1", "messages": [{"role": "user", "content": "x"}]},
    )
    # Resolve DB path via same layout as MemoryService
    from openevo.config.settings import get_settings

    db = get_settings().resolve_data_dir() / "memory.sqlite3"
    assert db.exists()
    conn = sqlite3.connect(db)
    try:
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row and str(row[0]).upper() == "WAL"
    finally:
        conn.close()
