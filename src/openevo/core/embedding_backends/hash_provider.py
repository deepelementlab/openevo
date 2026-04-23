from __future__ import annotations

from openevo.core.embeddings import text_embedding
from openevo.core.stores.base import EmbeddingProvider


class HashEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int = 128) -> None:
        self._dimension = max(8, int(dimension))

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list[float]:
        return text_embedding(text, self._dimension)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]
