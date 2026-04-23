"""Experience relation graph: causal inference and strategy-chain search."""

from __future__ import annotations

from collections import deque

from openevo.core.embeddings import cosine_similarity
from openevo.core.experience_models import Experience, ExperienceID, PredictedOutcome, Relation
from openevo.core.stores.base import EmbeddingProvider, GraphStore, VectorStore


class ExperienceGraph:
    def __init__(
        self,
        graph_store: GraphStore,
        vector_store: VectorStore,
        embedding: EmbeddingProvider,
    ) -> None:
        self._graph_store = graph_store
        self._vector_store = vector_store
        self._embedding = embedding

    def link(
        self,
        from_id: ExperienceID,
        relation: Relation,
        to_id: ExperienceID,
        confidence: float = 1.0,
    ) -> None:
        self._graph_store.add_edge(from_id, to_id, relation, confidence)

    def causal_inference(
        self,
        observed_exp_ids: list[ExperienceID],
        max_depth: int = 3,
    ) -> list[PredictedOutcome]:
        outcomes: dict[ExperienceID, tuple[float, str]] = {}
        for obs in observed_exp_ids:
            visited: set[tuple[str, str]] = set()
            queue: deque[tuple[str, int, float]] = deque([(obs, 0, 1.0)])
            while queue:
                node, depth, conf = queue.popleft()
                if depth >= max_depth:
                    continue
                for target, rel, edge_conf in self._graph_store.out_edges(node):
                    if rel != Relation.CAUSES:
                        continue
                    key = (node, target)
                    if key in visited:
                        continue
                    visited.add(key)
                    next_conf = conf * edge_conf
                    prev = outcomes.get(target)
                    if prev is None or next_conf > prev[0]:
                        outcomes[target] = (next_conf, f"caused_from={node}")
                    queue.append((target, depth + 1, next_conf))
        return [
            PredictedOutcome(experience_id=eid, confidence=c, rationale=r)
            for eid, (c, r) in sorted(outcomes.items(), key=lambda x: -x[1][0])
        ]

    def find_strategy_chain(
        self,
        goal_text: str,
        current_state_ids: list[ExperienceID],
        max_steps: int = 8,
        goal_threshold: float = 0.35,
    ) -> list[Experience]:
        all_exps = {e.id: e for e in self._vector_store.list_all()}
        goal_vec = self._embedding.embed(goal_text)

        def goal_score(exp: Experience) -> float:
            return cosine_similarity(exp.vector, goal_vec)

        frontier: list[tuple[float, ExperienceID, list[Experience]]] = []
        for sid in current_state_ids:
            if sid in all_exps:
                e = all_exps[sid]
                frontier.append((goal_score(e), sid, [e]))

        best_chain: list[Experience] = []
        best_score = -1.0
        seen_paths: set[tuple[ExperienceID, ...]] = set()

        while frontier:
            frontier.sort(key=lambda x: -x[0])
            score, node_id, chain = frontier.pop(0)
            if score > best_score:
                best_score = score
                best_chain = chain
            if score >= goal_threshold:
                return chain
            if len(chain) >= max_steps:
                continue
            for target, rel, _ in self._graph_store.out_edges(node_id):
                if rel not in (Relation.REFINES, Relation.REQUIRES):
                    continue
                if target not in all_exps:
                    continue
                exp = all_exps[target]
                path_key = tuple(e.id for e in chain + [exp])
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)
                frontier.append((goal_score(exp), target, chain + [exp]))

        return best_chain
