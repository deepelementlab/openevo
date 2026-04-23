"""Experience listing, trade, and lightweight strategy evolution."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from openevo.core.experience_models import (
    EvolvedStrategy,
    ExperienceID,
    ExperienceListing,
)
from openevo.core.experience_space import ExperienceSpace


class EvolutionMarket:
    def __init__(self, exp_space: ExperienceSpace) -> None:
        self.exp_space = exp_space
        self.ledger: dict[str, float] = defaultdict(float)
        self.reputation: dict[str, float] = defaultdict(lambda: 1.0)
        self.listings: dict[str, ExperienceListing] = {}

    def list_experience(
        self,
        seller_id: str,
        exp_id: ExperienceID,
        price: float,
        auction: bool = False,
    ) -> str:
        lid = str(uuid.uuid4())
        self.listings[lid] = ExperienceListing(
            listing_id=lid,
            seller=seller_id,
            experience_id=exp_id,
            price=float(price),
            auction=auction,
        )
        return lid

    def trade(self, buyer_id: str, listing_id: str) -> dict[str, Any]:
        listing = self.listings.get(listing_id)
        if not listing:
            return {"ok": False, "error": "listing_not_found"}
        price = listing.price
        if self.ledger[buyer_id] < price:
            self.ledger[buyer_id] += max(price, 10.0)
        self.ledger[buyer_id] -= price
        self.ledger[listing.seller] += price * 0.9
        self.reputation[listing.seller] += 0.05
        exp = self.exp_space.get(listing.experience_id)
        del self.listings[listing_id]
        return {
            "ok": True,
            "buyer": buyer_id,
            "experience_id": listing.experience_id,
            "price": price,
            "summary": exp.content_summary if exp else "",
        }

    def evaluate_experience(
        self,
        exp_id: ExperienceID,
        evaluators: list[str],
    ) -> float:
        exp = self.exp_space.get(exp_id)
        if not exp:
            return 0.0
        base = 0.5
        for ev in evaluators:
            base += 0.1 * self.reputation.get(ev, 1.0)
        return min(1.0, base)

    def evolve_strategy(
        self,
        domain: str,
        participants: list[str],
    ) -> EvolvedStrategy:
        pattern_keys: list[str] = []
        for pid in participants:
            hits = self.exp_space.query(
                domain,
                filters={"domain": domain, "source_agent": pid},
                top_k=15,
            )
            for h in hits:
                pattern_keys.append(f"{pid}:{h.content_summary[:80]}")
        summary = f"Evolved strategy for {domain} from {len(participants)} agents; patterns={len(pattern_keys)}"
        rewards = {p: 1.0 + 0.01 * len(pattern_keys) for p in participants}
        for p, r in rewards.items():
            self.ledger[p] += r
        return EvolvedStrategy(
            domain=domain,
            summary=summary,
            pattern_keys=pattern_keys[:50],
            participant_rewards=dict(rewards),
        )
