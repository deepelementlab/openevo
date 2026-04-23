"""End-to-end Open Experience Space: ingest, graph, agents, market."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openevo.api.server import create_app
from openevo.config.settings import clear_settings_cache


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    clear_settings_cache()
    monkeypatch.setenv("OPENEVO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OPENEVO_EXPERIENCE__ENABLED", "true")
    clear_settings_cache()
    app = create_app()
    with TestClient(app) as c:
        yield c
    clear_settings_cache()


def test_experience_ingest_query_compose(client: TestClient) -> None:
    r = client.post(
        "/api/v1/experience/ingest",
        json={
            "raw": {
                "content": {"summary": "alpha", "domain": "ml", "modality": "text"},
                "lessons": ["keep learning rate low"],
            },
            "source": "test",
            "source_agent": "agent-a",
        },
    )
    assert r.status_code == 200
    eid_a = r.json()["experience_id"]

    r = client.post(
        "/api/v1/experience/ingest",
        json={
            "raw": {
                "content": {"summary": "beta", "domain": "ml", "modality": "text"},
            },
            "source": "test",
            "source_agent": "agent-b",
        },
    )
    assert r.status_code == 200
    eid_b = r.json()["experience_id"]

    r = client.post(
        "/api/v1/experience/query",
        json={"query": "machine learning training", "filters": {"domain": "ml"}, "top_k": 5},
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 2

    r = client.post(
        "/api/v1/experience/compose",
        json={"experience_ids": [eid_a, eid_b], "strategy": "consensus_merge"},
    )
    assert r.status_code == 200
    assert r.json()["composite_id"]


def test_graph_causal_and_strategy_chain(client: TestClient) -> None:
    r = client.post(
        "/api/v1/experience/ingest",
        json={
            "raw": {"content": {"summary": "root cause", "domain": "ops"}},
            "metadata": {},
            "source_agent": "s1",
        },
    )
    cause = r.json()["experience_id"]
    r = client.post(
        "/api/v1/experience/ingest",
        json={
            "raw": {"content": {"summary": "outcome symptom", "domain": "ops"}},
            "source_agent": "s2",
        },
    )
    effect = r.json()["experience_id"]
    r = client.post(
        "/api/v1/experience/graph/link",
        json={"from_id": cause, "to_id": effect, "relation": "causes", "confidence": 0.9},
    )
    assert r.status_code == 200

    r = client.post(
        "/api/v1/experience/graph/causal",
        json={"observed_ids": [cause], "max_depth": 3},
    )
    assert r.status_code == 200
    preds = r.json()["predictions"]
    assert any(p["experience_id"] == effect for p in preds)

    r = client.post(
        "/api/v1/experience/graph/strategy_chain",
        json={"goal": "ops reliability", "current_state_ids": [cause], "max_steps": 4},
    )
    assert r.status_code == 200
    assert isinstance(r.json()["chain"], list)


def test_adapter_chat_ingest(client: TestClient) -> None:
    r = client.post(
        "/api/v1/experience/ingest",
        json={
            "raw": {
                "content": {
                    "messages": [
                        {"role": "user", "content": "choose A or B?"},
                        {"role": "assistant", "content": "choose A"},
                    ],
                    "domain": "dialogue",
                }
            },
            "adapter": "chat",
            "source": "hook",
            "source_agent": "claude",
        },
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_agents_collaborate_and_market(client: TestClient) -> None:
    client.post(
        "/api/v1/experience/ingest",
        json={
            "raw": {"content": {"summary": "frontend pattern", "domain": "frontend"}},
            "source_agent": "fe",
        },
    )
    client.post(
        "/api/v1/agents/register",
        json={"agent_id": "alpha", "capabilities": ["frontend"]},
    )
    client.post(
        "/api/v1/agents/register",
        json={"agent_id": "beta", "capabilities": ["frontend", "review"]},
    )
    r = client.post(
        "/api/v1/agents/collaborate",
        json={
            "requester_id": "alpha",
            "task_domain": "frontend",
            "required_capabilities": ["review"],
        },
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]
    r = client.post(
        "/api/v1/agents/collaborate/decide",
        json={"session_id": sid, "options": ["vue", "react"], "strategy": "expertise"},
    )
    assert r.status_code == 200
    assert r.json()["choice"] in ("vue", "react")

    r = client.post(
        "/api/v1/experience/ingest",
        json={
            "raw": {"content": {"summary": "listed gem", "domain": "trade"}},
            "source_agent": "alpha",
        },
    )
    eid = r.json()["experience_id"]
    r = client.post(
        "/api/v1/market/list",
        json={"seller_id": "alpha", "experience_id": eid, "price": 2.0},
    )
    assert r.status_code == 200
    lid = r.json()["listing_id"]
    r = client.post(
        "/api/v1/market/trade", json={"buyer_id": "beta", "listing_id": lid}
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True

    r = client.post(
        "/api/v1/market/evolve",
        json={"domain": "trade", "participants": ["alpha", "beta"]},
    )
    assert r.status_code == 200
    assert "summary" in r.json()
