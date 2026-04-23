from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from openevo.connectors import get_adapter
from openevo.core.experience_models import (
    CompositionStrategy,
    QueryStrategy,
    RawExperience,
)
from openevo.core.experience_space import ExperienceSpace, experience_to_dict

router = APIRouter(prefix="/api/v1/experience", tags=["experience"])


def _exp(request: Request) -> ExperienceSpace:
    space = getattr(request.app.state, "experience_space", None)
    if space is None:
        raise HTTPException(status_code=503, detail="Experience space disabled")
    return space  # type: ignore[no-any-return]


class RawExperienceInput(BaseModel):
    content: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    lessons: list[str] = Field(default_factory=list)
    outcome: str | None = None


class IngestPayload(BaseModel):
    raw: RawExperienceInput
    source: str = "api"
    adapter: str | None = Field(
        default=None,
        description="code|chat|error|doc|tool — extract list then ingest first",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_agent: str = "api"


class QueryPayload(BaseModel):
    query: str
    filters: dict[str, Any] = Field(default_factory=dict)
    top_k: int = 10
    strategy: QueryStrategy = QueryStrategy.HYBRID


class ComposePayload(BaseModel):
    experience_ids: list[str]
    strategy: CompositionStrategy = CompositionStrategy.CONSENSUS_MERGE


class GraphLinkPayload(BaseModel):
    from_id: str
    to_id: str
    relation: str
    confidence: float = 1.0


class CausalPayload(BaseModel):
    observed_ids: list[str]
    max_depth: int = 3


class StrategyChainPayload(BaseModel):
    goal: str
    current_state_ids: list[str]
    max_steps: int = 8


@router.post("/ingest")
def ingest_experience(request: Request, payload: IngestPayload) -> dict[str, Any]:
    space = _exp(request)
    if payload.adapter:
        ad = get_adapter(payload.adapter)
        if not ad:
            raise HTTPException(400, f"unknown adapter {payload.adapter}")
        raws = ad.extract(payload.raw.model_dump())
        if not raws:
            raws = [
                RawExperience(
                    content=payload.raw.content,
                    context=payload.raw.context,
                    lessons=payload.raw.lessons,
                    outcome=payload.raw.outcome,
                )
            ]
        ids = [
            space.ingest(
                r,
                source=payload.source,
                metadata=dict(payload.metadata),
                source_agent=payload.source_agent,
            )
            for r in raws
        ]
        return {"experience_ids": ids, "count": len(ids)}
    raw = RawExperience(
        content=payload.raw.content,
        context=payload.raw.context,
        lessons=payload.raw.lessons,
        outcome=payload.raw.outcome,
    )
    eid = space.ingest(
        raw,
        source=payload.source,
        metadata=payload.metadata,
        source_agent=payload.source_agent,
    )
    return {"experience_id": eid}


@router.post("/query")
def query_experience(request: Request, payload: QueryPayload) -> dict[str, Any]:
    space = _exp(request)
    hits = space.query(
        payload.query,
        filters=payload.filters or None,
        top_k=payload.top_k,
        strategy=payload.strategy,
    )
    return {"data": [experience_to_dict(e) for e in hits], "count": len(hits)}


@router.post("/compose")
def compose_experiences(request: Request, payload: ComposePayload) -> dict[str, Any]:
    space = _exp(request)
    comp = space.compose(payload.experience_ids, payload.strategy)
    return {
        "composite_id": comp.id,
        "source_ids": comp.source_ids,
        "summary": comp.summary,
        "vector": comp.vector,
        "metadata": comp.metadata,
    }


@router.get("/{exp_id}")
def get_experience(request: Request, exp_id: str) -> dict[str, Any]:
    space = _exp(request)
    exp = space.get(exp_id)
    if not exp:
        raise HTTPException(404, "not found")
    return experience_to_dict(exp)


@router.post("/graph/link")
def graph_link(request: Request, payload: GraphLinkPayload) -> dict[str, str]:
    space = _exp(request)
    from openevo.core.experience_models import Relation

    try:
        rel = Relation(payload.relation)
    except ValueError:
        rel = Relation.SIMILAR
    space.graph.link(payload.from_id, rel, payload.to_id, payload.confidence)
    return {"status": "linked"}


@router.post("/graph/causal")
def graph_causal(request: Request, payload: CausalPayload) -> dict[str, Any]:
    space = _exp(request)
    preds = space.graph.causal_inference(payload.observed_ids, payload.max_depth)
    return {
        "predictions": [
            {"experience_id": p.experience_id, "confidence": p.confidence, "rationale": p.rationale}
            for p in preds
        ]
    }


@router.post("/graph/strategy_chain")
def graph_strategy_chain(
    request: Request, payload: StrategyChainPayload
) -> dict[str, Any]:
    space = _exp(request)
    chain = space.graph.find_strategy_chain(
        payload.goal,
        payload.current_state_ids,
        max_steps=payload.max_steps,
    )
    return {"chain": [experience_to_dict(e) for e in chain]}
