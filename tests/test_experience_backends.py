from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openevo.api.server import create_app
from openevo.config.settings import clear_settings_cache
from openevo.core.embedding_backends.hash_provider import HashEmbeddingProvider
from openevo.core.stores.sqlite_graph import SQLiteGraphStore
from openevo.core.stores.sqlite_vector import SQLiteVectorStore


@pytest.fixture()
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clear_settings_cache()
    monkeypatch.setenv("OPENEVO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OPENEVO_EXPERIENCE__ENABLED", "true")
    clear_settings_cache()
    app = create_app()
    with TestClient(app) as client:
        yield client
    clear_settings_cache()


def test_default_degrade_to_sqlite_hash(app_client: TestClient) -> None:
    space = app_client.app.state.experience_space
    assert space is not None
    assert isinstance(space._vector_store, SQLiteVectorStore)
    assert isinstance(space._graph_store, SQLiteGraphStore)
    assert isinstance(space._embedder, HashEmbeddingProvider)


def test_external_backend_unavailable_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_settings_cache()
    monkeypatch.setenv("OPENEVO_DATA_DIR", str(tmp_path / "data2"))
    monkeypatch.setenv("OPENEVO_EXPERIENCE__ENABLED", "true")
    monkeypatch.setenv("OPENEVO_EXPERIENCE__VECTOR_STORE_BACKEND", "qdrant")
    monkeypatch.setenv("OPENEVO_EXPERIENCE__GRAPH_STORE_BACKEND", "neo4j")
    monkeypatch.setenv("OPENEVO_EXPERIENCE__EMBEDDING_PROVIDER", "sentence_transformer")
    monkeypatch.setenv("OPENEVO_EXPERIENCE__FALLBACK_ON_ERROR", "true")
    clear_settings_cache()

    app = create_app()
    with TestClient(app) as client:
        space = client.app.state.experience_space
        assert isinstance(space._vector_store, SQLiteVectorStore)
        assert isinstance(space._graph_store, SQLiteGraphStore)
        assert isinstance(space._embedder, HashEmbeddingProvider)

        r = client.post(
            "/api/v1/experience/ingest",
            json={
                "raw": {"content": {"summary": "fallback works", "domain": "test"}},
                "source_agent": "t1",
            },
        )
        assert r.status_code == 200
