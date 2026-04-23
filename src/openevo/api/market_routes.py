from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from openevo.core.evolution_market import EvolutionMarket

router = APIRouter(prefix="/api/v1/market", tags=["market"])


def _market(request: Request) -> EvolutionMarket:
    m = getattr(request.app.state, "evolution_market", None)
    if m is None:
        raise HTTPException(status_code=503, detail="Evolution market disabled")
    return m  # type: ignore[no-any-return]


class ListPayload(BaseModel):
    seller_id: str
    experience_id: str
    price: float = 1.0
    auction: bool = False


class TradePayload(BaseModel):
    buyer_id: str
    listing_id: str


class EvaluatePayload(BaseModel):
    experience_id: str
    evaluators: list[str] = Field(default_factory=list)


class EvolvePayload(BaseModel):
    domain: str
    participants: list[str] = Field(default_factory=list)


@router.post("/list")
def list_experience(request: Request, payload: ListPayload) -> dict[str, str]:
    m = _market(request)
    lid = m.list_experience(
        payload.seller_id, payload.experience_id, payload.price, payload.auction
    )
    return {"listing_id": lid}


@router.post("/trade")
def trade_experience(request: Request, payload: TradePayload) -> dict[str, object]:
    m = _market(request)
    return m.trade(payload.buyer_id, payload.listing_id)


@router.post("/evaluate")
def evaluate_experience(request: Request, payload: EvaluatePayload) -> dict[str, float]:
    m = _market(request)
    score = m.evaluate_experience(payload.experience_id, payload.evaluators)
    return {"score": score}


@router.post("/evolve")
def evolve_strategy(request: Request, payload: EvolvePayload) -> dict[str, object]:
    m = _market(request)
    strat = m.evolve_strategy(payload.domain, payload.participants)
    return {
        "domain": strat.domain,
        "summary": strat.summary,
        "pattern_keys": strat.pattern_keys,
        "participant_rewards": strat.participant_rewards,
    }
