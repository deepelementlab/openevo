"""Multi-agent coordination on top of Open Experience Space."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from openevo.core.embeddings import cosine_similarity, text_embedding
from openevo.core.experience_models import (
    Experience,
    ExperienceID,
    RawExperience,
    Visibility,
    AgentProfile,
)
from openevo.core.experience_space import ExperienceSpace


@dataclass
class AgentHandle:
    profile: AgentProfile
    protocol: AgentCoordinationProtocol

    def share(
        self,
        raw: RawExperience,
        source: str,
        visibility: Visibility = Visibility.PUBLIC,
        metadata: dict[str, Any] | None = None,
    ) -> ExperienceID:
        return self.protocol.share_experience(
            self.profile.id, raw, source, visibility, metadata
        )


@dataclass
class CollaborationSession:
    id: str
    task_domain: str
    participants: list[str]
    exp_space: ExperienceSpace
    shared_experience_ids: list[ExperienceID] = field(default_factory=list)

    def collective_decide(
        self,
        options: list[str],
        strategy: Literal["consensus", "expertise"] = "expertise",
    ) -> dict[str, Any]:
        """Score options by similarity of agent-tagged experiences to each option."""
        scores: dict[str, float] = {o: 0.0 for o in options}
        for agent_id in self.participants:
            exps = self.exp_space.query(
                self.task_domain,
                filters={"domain": self.task_domain, "source_agent": agent_id},
                top_k=20,
            )
            if not exps:
                exps = self.exp_space.query(
                    self.task_domain, filters={"source_agent": agent_id}, top_k=10
                )
            weight = 1.0 + 0.1 * len(exps)
            for opt in options:
                ov = text_embedding(opt, len(exps[0].vector) if exps else 128)
                for exp in exps:
                    scores[opt] += weight * cosine_similarity(ov, exp.vector)
        best = max(scores, key=scores.get)  # type: ignore[arg-type,return-value]
        return {"choice": best, "scores": scores, "strategy": strategy}

    def synthesize_learnings(self) -> ExperienceID:
        """Merge participant experiences in this domain into one composite record."""
        texts: list[str] = []
        for agent_id in self.participants:
            hits = self.exp_space.query(
                f"{self.task_domain} collaboration",
                filters={"source_agent": agent_id},
                top_k=5,
            )
            for h in hits:
                texts.append(h.content_summary)
        raw = RawExperience(
            content={
                "summary": f"session:{self.id} synthesis",
                "domain": self.task_domain,
                "modality": "structured",
                "snippets": texts[:50],
            },
            context={"session_id": self.id, "participants": self.participants},
            lessons=[f"collaboration_{self.task_domain}"],
        )
        eid = self.exp_space.ingest(
            raw,
            source="collaboration",
            metadata={"session_id": self.id},
            source_agent="coordination",
        )
        self.shared_experience_ids.append(eid)
        return eid


class AgentCoordinationProtocol:
    def __init__(self, exp_space: ExperienceSpace) -> None:
        self.exp_space = exp_space
        self.agents: dict[str, AgentProfile] = {}
        self._sessions: dict[str, CollaborationSession] = {}

    def register_agent(
        self,
        agent_id: str,
        capabilities: list[str],
        initial_experiences: list[ExperienceID] | None = None,
        team_id: str | None = None,
    ) -> AgentHandle:
        pool = set(initial_experiences or [])
        profile = AgentProfile(
            id=agent_id,
            capabilities=list(capabilities),
            experience_pool=pool,
            team_id=team_id,
        )
        self.agents[agent_id] = profile
        for eid in pool:
            self.exp_space.add_contributor(eid, agent_id)
        return AgentHandle(profile, self)

    def share_experience(
        self,
        agent_id: str,
        raw: RawExperience,
        source: str,
        visibility: Visibility = Visibility.PUBLIC,
        metadata: dict[str, Any] | None = None,
    ) -> ExperienceID:
        meta = dict(metadata or {})
        meta["visibility"] = visibility.value
        if visibility == Visibility.TEAM and self.agents.get(agent_id):
            meta["team_id"] = self.agents[agent_id].team_id
        eid = self.exp_space.ingest(raw, source=source, metadata=meta, source_agent=agent_id)
        if agent_id in self.agents:
            self.agents[agent_id].experience_pool.add(eid)
        return eid

    def request_collaboration(
        self,
        requester_id: str,
        task_domain: str,
        required_capabilities: list[str],
    ) -> CollaborationSession:
        matches: list[str] = []
        for aid, prof in self.agents.items():
            if aid == requester_id:
                continue
            if not required_capabilities:
                matches.append(aid)
                continue
            if any(c in prof.capabilities for c in required_capabilities):
                matches.append(aid)
        sid = str(uuid.uuid4())
        participants = [requester_id, *matches[:5]]
        session = CollaborationSession(
            id=sid,
            task_domain=task_domain,
            participants=participants,
            exp_space=self.exp_space,
        )
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> CollaborationSession | None:
        return self._sessions.get(session_id)
