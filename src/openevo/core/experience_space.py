"""Open Experience Space — ingest, query, compose with pluggable backends."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openevo.config.settings import OpenEvoConfig
from openevo.core.experience_graph import ExperienceGraph
from openevo.core.experience_models import (
    CanonicalExperience,
    CompositionStrategy,
    CompositeExperience,
    Experience,
    ExperienceID,
    QueryStrategy,
    RawExperience,
    Relation,
)
from openevo.core.experience_store import new_experience_id
from openevo.core.stores.factory import StoreFactory


class ExperienceSpace:
    """Unified experience space with fallback-capable storage backend factory."""

    def __init__(self, data_dir: Path, cfg: OpenEvoConfig | None = None) -> None:
        self._cfg = cfg
        exp_dir = data_dir / "experience"
        exp_dir.mkdir(parents=True, exist_ok=True)

        es = cfg.experience if cfg else None
        self._embedder = StoreFactory.create_embedding(es) if es else StoreFactory.create_embedding(_default_es())
        self._dim = self._embedder.dimension
        self._vector_store = (
            StoreFactory.create_vector_store(es, data_dir, self._dim)
            if es
            else StoreFactory.create_vector_store(_default_es(), data_dir, self._dim)
        )
        self._graph_store = (
            StoreFactory.create_graph_store(es, data_dir)
            if es
            else StoreFactory.create_graph_store(_default_es(), data_dir)
        )
        self._graph = ExperienceGraph(self._graph_store, self._vector_store, self._embedder)

    @property
    def graph(self) -> ExperienceGraph:
        return self._graph

    @property
    def store(self):
        return self._vector_store

    @property
    def dimension(self) -> int:
        return self._dim

    def _canonicalize(self, raw: RawExperience, source: str) -> CanonicalExperience:
        lessons = raw.lessons or raw.content.get("lessons") or []
        if isinstance(lessons, str):
            lessons = [lessons]
        modality = raw.content.get("modality") or source or "structured"
        domain = raw.content.get("domain") or raw.context.get("domain") or "general"
        summary_parts = []
        if raw.outcome:
            summary_parts.append(f"outcome: {raw.outcome}")
        if lessons:
            summary_parts.append("lessons: " + "; ".join(str(x) for x in lessons))
        summary_parts.append(str(raw.content.get("summary") or raw.content))
        summary = "\n".join(summary_parts)[:8000]
        payload = {
            **raw.content,
            "context": raw.context,
            "lessons": list(lessons),
            "outcome": raw.outcome,
            "source_connector": source,
        }
        return CanonicalExperience(
            summary=summary,
            payload=payload,
            modality=str(modality),
            domain=str(domain),
        )

    def ingest(
        self,
        raw: RawExperience,
        source: str,
        metadata: dict[str, Any] | None = None,
        source_agent: str = "system",
    ) -> ExperienceID:
        meta = dict(metadata or {})
        canonical = self._canonicalize(raw, source)
        vector = self._embedder.embed(canonical.to_text())
        eid = new_experience_id()
        relations_spec = meta.pop("relations", []) or []
        exp = Experience(
            id=eid,
            vector=vector,
            modality=canonical.modality,
            domain=canonical.domain,
            timestamp=datetime.now(tz=timezone.utc),
            source_agent=meta.get("source_agent", source_agent),
            content_summary=canonical.summary[:2000],
            content_payload=canonical.payload,
            metadata=meta,
        )
        self._vector_store.upsert(exp)
        self._graph_store.add_node(exp)
        for rel_item in relations_spec:
            if isinstance(rel_item, dict):
                tgt = rel_item.get("target")
                rel = rel_item.get("relation", "similar")
                conf = float(rel_item.get("confidence", 1.0))
                if tgt:
                    try:
                        r_enum = Relation(rel)
                    except ValueError:
                        r_enum = Relation.SIMILAR
                    self._graph_store.add_edge(eid, str(tgt), r_enum, conf)
        return eid

    def add_contributor(self, exp_id: ExperienceID, agent_id: str) -> None:
        exp = self._vector_store.get(exp_id)
        if not exp:
            return
        contribs = list(exp.metadata.get("contributors", []))
        if agent_id not in contribs:
            contribs.append(agent_id)
        exp.metadata["contributors"] = contribs
        self._vector_store.upsert(exp)

    def query(
        self,
        query: str | list[float],
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
        strategy: QueryStrategy = QueryStrategy.HYBRID,
    ) -> list[Experience]:
        qvec = self._embedder.embed(query) if isinstance(query, str) else query
        vector_hits = self._vector_store.search(qvec, filters or {}, top_k)
        if strategy == QueryStrategy.VECTOR:
            return [e for e, _ in vector_hits]

        seeds = [e for e, _ in vector_hits[: max(1, top_k // 2)]]
        expanded = _expand_graph(self._graph_store, self._vector_store, seeds)
        if strategy == QueryStrategy.GRAPH:
            return expanded[:top_k]

        merged: dict[str, Experience] = {e.id: e for e, _ in vector_hits}
        for e in expanded:
            merged[e.id] = e
        reranked = sorted(
            merged.values(),
            key=lambda e: _cos(qvec, e.vector),
            reverse=True,
        )
        return reranked[:top_k]

    def compose(
        self,
        exp_ids: list[ExperienceID],
        strategy: CompositionStrategy = CompositionStrategy.CONSENSUS_MERGE,
    ) -> CompositeExperience:
        exps = [self._vector_store.get(i) for i in exp_ids]
        exps = [e for e in exps if e is not None]
        if not exps:
            return CompositeExperience(
                id=new_experience_id(),
                source_ids=[],
                summary="empty",
                vector=self._embedder.embed("empty"),
            )
        if strategy == CompositionStrategy.CONCAT:
            summary = "\n---\n".join(e.content_summary for e in exps)
        else:
            summary = " | ".join(e.content_summary[:200] for e in exps)
        if strategy == CompositionStrategy.WEIGHTED_VECTOR:
            n = len(exps)
            dim = len(exps[0].vector)
            acc = [0.0] * dim
            for e in exps:
                for i, v in enumerate(e.vector):
                    acc[i] += v
            vector = [x / n for x in acc]
        else:
            vector = self._embedder.embed(summary)
        return CompositeExperience(
            id=new_experience_id(),
            source_ids=[e.id for e in exps],
            summary=summary[:8000],
            vector=vector,
            metadata={"strategy": strategy.value, "count": len(exps)},
        )

    def get(self, exp_id: ExperienceID) -> Experience | None:
        return self._vector_store.get(exp_id)


def _expand_graph(graph_store, vector_store, seeds: list[Experience]) -> list[Experience]:
    seen: set[ExperienceID] = set()
    out: list[Experience] = []
    for e in seeds:
        if e.id in seen:
            continue
        seen.add(e.id)
        out.append(e)
        for target_id, _, _ in graph_store.out_edges(e.id):
            if target_id in seen:
                continue
            nexp = vector_store.get(target_id)
            if nexp:
                seen.add(target_id)
                out.append(nexp)
        for from_id, _, _ in graph_store.in_edges(e.id):
            if from_id in seen:
                continue
            nexp = vector_store.get(from_id)
            if nexp:
                seen.add(from_id)
                out.append(nexp)
    return out


def experience_to_dict(exp: Experience) -> dict[str, Any]:
    d = asdict(exp)
    d["timestamp"] = exp.timestamp.isoformat()
    return d


def _cos(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5 or 1.0
    nb = sum(x * x for x in b) ** 0.5 or 1.0
    return dot / (na * nb)


def _default_es():
    from openevo.config.settings import ExperienceSettings

    return ExperienceSettings()
