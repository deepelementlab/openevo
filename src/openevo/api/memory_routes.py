from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from openevo.core.memory import MemoryService
from openevo.core.observer import get_observer

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


class GroupMessage(BaseModel):
    role: str = "user"
    content: str
    timestamp: int | None = None


class GroupPayload(BaseModel):
    group_id: str = "default"
    user_id: str = "openevo-user"
    messages: list[GroupMessage] = Field(default_factory=list)


class SearchPayload(BaseModel):
    query: str
    top_k: int = 5
    filters: dict[str, Any] | None = None


class GetPayload(BaseModel):
    filters: dict[str, Any] | None = None
    page: int = 1
    page_size: int = 50


class CuratedPayload(BaseModel):
    action: str  # add | remove | replace
    target: str = "memory"  # memory | user
    content: str | None = None
    old_text: str | None = None
    score: float = 0.5
    source: str = "api"


class GroupMemoryAccepted(BaseModel):
    """Response for episodic batch ingest."""

    message: str
    status: str | None = None
    count: int | None = None
    request_id: str | None = None


class CuratedMemoryResult(BaseModel):
    """Curated memory mutation result (success or error fields)."""

    model_config = ConfigDict(extra="allow")

    success: bool
    message: str | None = None
    target: str | None = None
    error: str | None = None


def _svc(request: Request) -> MemoryService:
    return request.app.state.memory  # type: ignore[no-any-return]


@router.post("/group", response_model=GroupMemoryAccepted)
def add_group_memory(request: Request, payload: GroupPayload) -> dict[str, Any]:
    svc = _svc(request)
    obs = get_observer()
    msgs = [m.model_dump() for m in payload.messages]
    result = svc.append_episodic(payload.group_id, payload.user_id, msgs)
    obs.record(
        phase="post",
        session_id=payload.group_id,
        tool_name="memory_group",
        tool_input={"n": len(msgs)},
        tool_output=result,
        source="api",
    )
    return {"message": "accepted", **result}


@router.post("")
def add_memory_alias(request: Request, payload: GroupPayload) -> dict[str, Any]:
    return add_group_memory(request, payload)


@router.post("/search")
def search_memories(request: Request, payload: SearchPayload) -> dict[str, Any]:
    svc = _svc(request)
    gid = None
    if payload.filters:
        gid = payload.filters.get("group_id")
    data = svc.search_episodic(payload.query, gid, top_k=payload.top_k)
    return {"data": {"memories": data, "count": len(data)}}


@router.post("/get")
def get_memories(request: Request, payload: GetPayload) -> dict[str, Any]:
    svc = _svc(request)
    gid = None
    if payload.filters:
        gid = payload.filters.get("group_id")
    data = svc.get_episodic(gid, payload.page, payload.page_size)
    return {"data": data}


@router.post("/curated", response_model=CuratedMemoryResult)
def curated_memory(request: Request, payload: CuratedPayload) -> dict[str, Any]:
    svc = _svc(request)
    obs = get_observer()
    if payload.action == "add":
        r = svc.add(
            payload.target,
            str(payload.content or ""),
            source=payload.source,
            score=payload.score,
        )
    elif payload.action == "remove":
        r = svc.remove(payload.target, str(payload.old_text or ""))
    elif payload.action == "replace":
        r = svc.replace(
            payload.target,
            str(payload.old_text or ""),
            str(payload.content or ""),
            source=payload.source,
            score=payload.score,
        )
    else:
        return {"success": False, "error": "unknown action"}
    obs.record(
        phase="post",
        session_id="curated",
        tool_name=f"memory_{payload.action}",
        tool_input=payload.model_dump(),
        tool_output=r,
        is_error=not r.get("success", True),
        source="api",
    )
    return r
