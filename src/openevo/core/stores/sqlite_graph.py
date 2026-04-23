from __future__ import annotations

from openevo.core.experience_models import Experience, ExperienceID, Relation
from openevo.core.experience_store import ExperienceSQLiteStore
from openevo.core.stores.base import GraphStore


class SQLiteGraphStore(GraphStore):
    def __init__(self, store: ExperienceSQLiteStore) -> None:
        self._store = store

    def add_node(self, exp: Experience) -> None:
        # Node payload already persisted via vector store upsert.
        _ = exp

    def add_edge(
        self,
        from_id: ExperienceID,
        to_id: ExperienceID,
        relation: Relation,
        confidence: float,
    ) -> None:
        self._store.add_edge(from_id, to_id, relation, confidence)

    def out_edges(self, from_id: ExperienceID) -> list[tuple[ExperienceID, Relation, float]]:
        return self._store.out_edges(from_id)

    def in_edges(self, to_id: ExperienceID) -> list[tuple[ExperienceID, Relation, float]]:
        return self._store.in_edges(to_id)
