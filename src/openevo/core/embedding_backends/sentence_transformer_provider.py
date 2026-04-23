from __future__ import annotations

import logging

from openevo.core.stores.base import EmbeddingProvider

log = logging.getLogger("openevo.embedding.sentence_transformer")


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
        normalize: bool = True,
        fallback_dim: int = 384,
    ) -> None:
        self._model = None
        self._normalize = normalize
        self._fallback_dim = fallback_dim
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name, device=device)
            self._dim = int(self._model.get_sentence_embedding_dimension())
            log.info("loaded sentence-transformer model=%s dim=%s", model_name, self._dim)
        except Exception as e:  # pragma: no cover - runtime optional dependency
            self._dim = fallback_dim
            log.warning("sentence-transformer unavailable: %s", e)

    @property
    def is_available(self) -> bool:
        return self._model is not None

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        if self._model is None:
            raise RuntimeError("sentence-transformer backend unavailable")
        vector = self._model.encode(
            text,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
        )
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            raise RuntimeError("sentence-transformer backend unavailable")
        vectors = self._model.encode(
            texts,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return [v.tolist() for v in vectors]
