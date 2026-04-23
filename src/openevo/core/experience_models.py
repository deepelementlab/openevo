"""Data models for Open Experience Space (OES)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

ExperienceID = str


class Relation(str, Enum):
    CAUSES = "causes"
    REQUIRES = "requires"
    REFINES = "refines"
    CONTRADICTS = "contradicts"
    SIMILAR = "similar"


class Visibility(str, Enum):
    PRIVATE = "private"
    TEAM = "team"
    PUBLIC = "public"


class CompositionStrategy(str, Enum):
    CONCAT = "concat"
    CONSENSUS_MERGE = "consensus_merge"
    WEIGHTED_VECTOR = "weighted_vector"


class QueryStrategy(str, Enum):
    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"


@dataclass
class Experience:
    id: ExperienceID
    vector: list[float]
    modality: str
    domain: str
    timestamp: datetime
    source_agent: str
    content_summary: str
    content_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawExperience:
    """Universal raw payload before canonicalization."""

    content: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)
    lessons: list[str] = field(default_factory=list)
    outcome: str | None = None


@dataclass
class CanonicalExperience:
    summary: str
    payload: dict[str, Any]
    modality: str
    domain: str

    def to_text(self) -> str:
        parts = [self.summary, str(self.payload), " ".join(self.payload.get("lessons", []))]
        return "\n".join(p for p in parts if p)


@dataclass
class CompositeExperience:
    id: str
    source_ids: list[ExperienceID]
    summary: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictedOutcome:
    experience_id: ExperienceID
    confidence: float
    rationale: str


@dataclass
class AgentProfile:
    id: str
    capabilities: list[str]
    experience_pool: set[ExperienceID] = field(default_factory=set)
    team_id: str | None = None


@dataclass
class ExperienceListing:
    listing_id: str
    seller: str
    experience_id: ExperienceID
    price: float
    auction: bool = False


@dataclass
class EvolvedStrategy:
    domain: str
    summary: str
    pattern_keys: list[str]
    participant_rewards: dict[str, float]
