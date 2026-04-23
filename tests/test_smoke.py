from __future__ import annotations

import os
import tempfile
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


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_memory_group_and_search(client: TestClient) -> None:
    r = client.post(
        "/api/v1/memories/group",
        json={
            "group_id": "g1",
            "user_id": "u1",
            "messages": [{"role": "user", "content": "hello openevo world"}],
        },
    )
    assert r.status_code == 200
    r2 = client.post(
        "/api/v1/memories/search",
        json={"query": "openevo", "top_k": 5, "filters": {"group_id": "g1"}},
    )
    assert r2.status_code == 200
    data = r2.json()["data"]["memories"]
    assert len(data) >= 1


def test_learning_cycle(client: TestClient) -> None:
    client.post(
        "/api/v1/learning/record",
        json={"tool_name": "bash", "tool_input": {}, "is_error": False},
    )
    r = client.get("/api/v1/learning/cycle", params={"dry_run": True})
    assert r.status_code == 200


def test_notes_orient(client: TestClient) -> None:
    r = client.get("/api/v1/notes/orient")
    assert r.status_code == 200
    body = r.json()
    assert "stats" in body
