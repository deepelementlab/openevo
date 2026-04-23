from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from openevo.core.experience_models import Experience, ExperienceID
from openevo.core.stores.base import VectorStore

log = logging.getLogger("openevo.stores.qdrant")


class QdrantVectorStore(VectorStore):
    def __init__(
        self,
        host: str,
        port: int,
        collection: str,
        dimension: int,
        api_key: str | None = None,
        prefer_grpc: bool = False,
    ) -> None:
        self._client = None
        self.collection = collection
        self.dimension = int(dimension)
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self._client = QdrantClient(
                host=host,
                port=port,
                api_key=api_key,
                prefer_grpc=prefer_grpc,
            )
            existing = {c.name for c in self._client.get_collections().collections}
            if collection not in existing:
                self._client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
                )
        except Exception as e:  # pragma: no cover
            log.warning("qdrant backend unavailable: %s", e)
            self._client = None

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def _ensure(self) -> None:
        if self._client is None:
            raise RuntimeError("qdrant backend unavailable")

    def upsert(self, exp: Experience) -> None:
        self._ensure()
        from qdrant_client.models import PointStruct

        self._client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=exp.id,
                    vector=exp.vector,
                    payload={
                        "modality": exp.modality,
                        "domain": exp.domain,
                        "source_agent": exp.source_agent,
                        "content_summary": exp.content_summary,
                        "content_payload": exp.content_payload,
                        "metadata": exp.metadata,
                        "timestamp": exp.timestamp.isoformat(),
                    },
                )
            ],
        )

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Any] | None,
        top_k: int,
    ) -> list[tuple[Experience, float]]:
        self._ensure()
        qfilter = None
        if filters:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            must = []
            for key in ("domain", "modality", "source_agent"):
                if key in filters:
                    must.append(FieldCondition(key=key, match=MatchValue(value=filters[key])))
            if must:
                qfilter = Filter(must=must)

        points = self._client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=qfilter,
            with_payload=True,
            limit=top_k,
        )
        out: list[tuple[Experience, float]] = []
        for p in points:
            payload = p.payload or {}
            ts = payload.get("timestamp")
            timestamp = datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.utcnow()
            out.append(
                (
                    Experience(
                        id=str(p.id),
                        vector=list(p.vector or []),
                        modality=str(payload.get("modality", "structured")),
                        domain=str(payload.get("domain", "general")),
                        timestamp=timestamp,
                        source_agent=str(payload.get("source_agent", "system")),
                        content_summary=str(payload.get("content_summary", "")),
                        content_payload=dict(payload.get("content_payload", {})),
                        metadata=dict(payload.get("metadata", {})),
                    ),
                    float(p.score or 0.0),
                )
            )
        return out

    def get(self, exp_id: ExperienceID) -> Experience | None:
        self._ensure()
        records = self._client.retrieve(
            collection_name=self.collection,
            ids=[exp_id],
            with_payload=True,
            with_vectors=True,
        )
        if not records:
            return None
        r = records[0]
        payload = r.payload or {}
        ts = payload.get("timestamp")
        timestamp = datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.utcnow()
        return Experience(
            id=str(r.id),
            vector=list(r.vector or []),
            modality=str(payload.get("modality", "structured")),
            domain=str(payload.get("domain", "general")),
            timestamp=timestamp,
            source_agent=str(payload.get("source_agent", "system")),
            content_summary=str(payload.get("content_summary", "")),
            content_payload=dict(payload.get("content_payload", {})),
            metadata=dict(payload.get("metadata", {})),
        )

    def list_all(self) -> list[Experience]:
        self._ensure()
        out: list[Experience] = []
        offset = None
        while True:
            points, offset = self._client.scroll(
                collection_name=self.collection,
                with_payload=True,
                with_vectors=True,
                limit=256,
                offset=offset,
            )
            for r in points:
                payload = r.payload or {}
                ts = payload.get("timestamp")
                timestamp = datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.utcnow()
                out.append(
                    Experience(
                        id=str(r.id),
                        vector=list(r.vector or []),
                        modality=str(payload.get("modality", "structured")),
                        domain=str(payload.get("domain", "general")),
                        timestamp=timestamp,
                        source_agent=str(payload.get("source_agent", "system")),
                        content_summary=str(payload.get("content_summary", "")),
                        content_payload=dict(payload.get("content_payload", {})),
                        metadata=dict(payload.get("metadata", {})),
                    )
                )
            if offset is None:
                break
        return out
