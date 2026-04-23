from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from openevo.core.notes import WikiStore
from openevo.core.observer import get_observer

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])


class PagePayload(BaseModel):
    section: str = "concepts"
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)


class QueryPayload(BaseModel):
    query: str
    limit: int = 10


class IngestPayload(BaseModel):
    title: str
    text: str
    section: str = "concepts"


def _wiki(request: Request) -> WikiStore:
    return request.app.state.wiki  # type: ignore[no-any-return]


@router.get("/orient")
def orient(request: Request, log_entries: int = 30) -> dict[str, object]:
    w = _wiki(request)
    obs = get_observer()
    payload = w.get_orient_payload(log_entries=min(120, max(1, log_entries)))
    obs.record(
        phase="post",
        session_id="notes",
        tool_name="wiki_orient",
        tool_input={"log_entries": log_entries},
        tool_output={"stats": payload.get("stats")},
        source="api",
    )
    return payload


@router.post("/page")
def write_page(request: Request, body: PagePayload) -> dict[str, str]:
    w = _wiki(request)
    path = w.write_page(body.section, body.title, body.body, tags=body.tags)
    get_observer().record(
        phase="post",
        session_id="notes",
        tool_name="wiki_write",
        tool_input=body.model_dump(),
        tool_output={"path": str(path)},
        source="api",
    )
    return {"path": str(path)}


@router.post("/query")
def query_wiki(request: Request, body: QueryPayload) -> dict[str, object]:
    w = _wiki(request)
    rows = w.query(body.query, limit=body.limit)
    get_observer().record(
        phase="post",
        session_id="notes",
        tool_name="wiki_query",
        tool_input=body.model_dump(),
        tool_output={"count": len(rows)},
        source="api",
    )
    return {"results": rows, "count": len(rows)}


@router.post("/ingest")
def ingest(request: Request, body: IngestPayload) -> dict[str, str]:
    w = _wiki(request)
    path = w.ingest_text(body.title, body.text, section=body.section)
    return {"path": str(path)}
