from __future__ import annotations

from typing import Any, Protocol

from openevo.core.experience_models import Experience, ExperienceID, Relation


class VectorStore(Protocol):
    def upsert(self, exp: Experience) -> None: ...

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Any] | None,
        top_k: int,
    ) -> list[tuple[Experience, float]]: ...

    def get(self, exp_id: ExperienceID) -> Experience | None: ...

    def list_all(self) -> list[Experience]: ...


class GraphStore(Protocol):
    def add_node(self, exp: Experience) -> None: ...

    def add_edge(
        self,
        from_id: ExperienceID,
        to_id: ExperienceID,
        relation: Relation,
        confidence: float,
    ) -> None: ...

    def out_edges(self, from_id: ExperienceID) -> list[tuple[ExperienceID, Relation, float]]: ...

    def in_edges(self, to_id: ExperienceID) -> list[tuple[ExperienceID, Relation, float]]: ...


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
