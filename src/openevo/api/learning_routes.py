from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from openevo.core.learning import LearningService
from openevo.core.observer import get_observer

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])


class RecordPayload(BaseModel):
    session_id: str = "default"
    tool_name: str
    tool_input: dict[str, Any] | None = None
    tool_output: dict[str, Any] | None = None
    is_error: bool = False


def _svc(request: Request) -> LearningService:
    return request.app.state.learning  # type: ignore[no-any-return]


@router.post("/record")
def record_observation(request: Request, payload: RecordPayload) -> dict[str, str]:
    get_observer().record(
        phase="api",
        session_id=payload.session_id,
        tool_name=payload.tool_name,
        tool_input=payload.tool_input,
        tool_output=payload.tool_output,
        is_error=payload.is_error,
        source="api",
    )
    return {"status": "ok"}


@router.post("/learn")
def learn(request: Request) -> dict[str, Any]:
    svc = _svc(request)
    instincts, msg = svc.learn_from_observations()
    return {
        "instincts": [i.__dict__ for i in instincts],
        "message": msg,
    }


@router.post("/evolve")
def evolve(request: Request, dry_run: bool = Query(True)) -> dict[str, Any]:
    svc = _svc(request)
    paths, msg = svc.evolve_skills(dry_run=dry_run)
    return {"paths": paths, "message": msg, "dry_run": dry_run}


@router.get("/cycle")
def cycle(request: Request, dry_run: bool = False) -> dict[str, Any]:
    svc = _svc(request)
    rep = svc.run_autonomous_cycle(dry_run=dry_run)
    return {
        "observations_processed": rep.observations_processed,
        "instincts_created": rep.instincts_created,
        "evolved_files": rep.evolved_files,
        "messages": rep.messages,
    }


@router.post("/ecap")
def save_ecap(request: Request, payload: dict[str, Any]) -> dict[str, str]:
    svc = _svc(request)
    path = svc.save_ecap(payload)
    return {"path": str(path)}
