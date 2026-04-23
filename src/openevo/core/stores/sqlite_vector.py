from __future__ import annotations

from openevo.core.embeddings import cosine_similarity
from openevo.core.experience_models import Experience, ExperienceID
from openevo.core.experience_store import ExperienceSQLiteStore
from openevo.core.stores.base import VectorStore


class SQLiteVectorStore(VectorStore):
    def __init__(self, store: ExperienceSQLiteStore) -> None:
        self._store = store

    def upsert(self, exp: Experience) -> None:
        self._store.upsert_experience(exp)

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, object] | None,
        top_k: int,
    ) -> list[tuple[Experience, float]]:
        filt = filters or {}
        scored: list[tuple[Experience, float]] = []
        for exp in self._store.iter_experiences():
            if not _match(exp, filt):
                continue
            scored.append((exp, cosine_similarity(query_vector, exp.vector)))
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def get(self, exp_id: ExperienceID) -> Experience | None:
        return self._store.get_experience(exp_id)

    def list_all(self) -> list[Experience]:
        return self._store.iter_experiences()


def _match(exp: Experience, filt: dict[str, object]) -> bool:
    if (d := filt.get("domain")) and exp.domain != d:
        return False
    if (m := filt.get("modality")) and exp.modality != m:
        return False
    if (a := filt.get("source_agent")) and exp.source_agent != a:
        return False
    return True
