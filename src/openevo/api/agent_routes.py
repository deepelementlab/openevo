from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from openevo.core.agent_coordination import AgentCoordinationProtocol
from openevo.core.experience_models import RawExperience, Visibility

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


def _coord(request: Request) -> AgentCoordinationProtocol:
    c = getattr(request.app.state, "agent_coord", None)
    if c is None:
        raise HTTPException(status_code=503, detail="Agent coordination disabled")
    return c  # type: ignore[no-any-return]


class RegisterPayload(BaseModel):
    agent_id: str
    capabilities: list[str] = Field(default_factory=list)
    initial_experience_ids: list[str] = Field(default_factory=list)
    team_id: str | None = None


class SharePayload(BaseModel):
    raw: dict[str, Any]
    source: str = "agent"
    visibility: Visibility = Visibility.PUBLIC
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollaboratePayload(BaseModel):
    requester_id: str
    task_domain: str
    required_capabilities: list[str] = Field(default_factory=list)


class DecidePayload(BaseModel):
    session_id: str
    options: list[str]
    strategy: str = "expertise"


class SynthesizePayload(BaseModel):
    session_id: str


@router.post("/register")
def register_agent(request: Request, payload: RegisterPayload) -> dict[str, Any]:
    coord = _coord(request)
    handle = coord.register_agent(
        payload.agent_id,
        payload.capabilities,
        payload.initial_experience_ids,
        payload.team_id,
    )
    return {
        "agent_id": handle.profile.id,
        "capabilities": handle.profile.capabilities,
        "experience_pool": list(handle.profile.experience_pool),
    }


@router.post("/{agent_id}/share")
def share_experience(
    request: Request, agent_id: str, payload: SharePayload
) -> dict[str, Any]:
    coord = _coord(request)
    raw = RawExperience(
        content=payload.raw.get("content", payload.raw),
        context=payload.raw.get("context", {}),
        lessons=list(payload.raw.get("lessons", [])),
        outcome=payload.raw.get("outcome"),
    )
    eid = coord.share_experience(
        agent_id, raw, payload.source, payload.visibility, payload.metadata
    )
    return {"experience_id": eid}


@router.post("/collaborate")
def request_collaboration(
    request: Request, payload: CollaboratePayload
) -> dict[str, Any]:
    coord = _coord(request)
    session = coord.request_collaboration(
        payload.requester_id,
        payload.task_domain,
        payload.required_capabilities,
    )
    return {
        "session_id": session.id,
        "participants": session.participants,
        "task_domain": session.task_domain,
    }


@router.post("/collaborate/decide")
def collaborate_decide(request: Request, payload: DecidePayload) -> dict[str, Any]:
    coord = _coord(request)
    session = coord.get_session(payload.session_id)
    if not session:
        raise HTTPException(404, "session not found")
    if payload.strategy not in ("expertise", "consensus"):
        payload.strategy = "expertise"
    return session.collective_decide(
        payload.options, strategy=payload.strategy  # type: ignore[arg-type]
    )


@router.post("/collaborate/synthesize")
def collaborate_synthesize(
    request: Request, payload: SynthesizePayload
) -> dict[str, Any]:
    coord = _coord(request)
    session = coord.get_session(payload.session_id)
    if not session:
        raise HTTPException(404, "session not found")
    eid = session.synthesize_learnings()
    return {"synthesized_experience_id": eid}
