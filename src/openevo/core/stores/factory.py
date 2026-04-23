from __future__ import annotations

import logging
from pathlib import Path

from openevo.config.settings import ExperienceSettings
from openevo.core.embedding_backends import (
    HashEmbeddingProvider,
    SentenceTransformerProvider,
)
from openevo.core.experience_store import ExperienceSQLiteStore
from openevo.core.stores.base import EmbeddingProvider, GraphStore, VectorStore
from openevo.core.stores.neo4j_store import Neo4jGraphStore
from openevo.core.stores.qdrant_store import QdrantVectorStore
from openevo.core.stores.sqlite_graph import SQLiteGraphStore
from openevo.core.stores.sqlite_vector import SQLiteVectorStore

log = logging.getLogger("openevo.stores.factory")


class StoreFactory:
    @staticmethod
    def create_embedding(settings: ExperienceSettings) -> EmbeddingProvider:
        provider = (settings.embedding.provider or settings.embedding_provider).lower()
        dimension = settings.embedding.dimension or settings.embedding_dim
        model_name = settings.embedding.model_name or settings.embedding_model_name
        device = settings.embedding.device or settings.embedding_device
        normalize = settings.embedding.normalize if settings.embedding else settings.embedding_normalize
        if provider == "sentence_transformer":
            st = SentenceTransformerProvider(
                model_name=model_name,
                device=device,
                normalize=normalize,
                fallback_dim=dimension,
            )
            if st.is_available:
                return st
            if not settings.fallback_on_error:
                raise RuntimeError("sentence_transformer embedding unavailable")
            log.warning("fallback to hash embedding provider")
        return HashEmbeddingProvider(dimension=dimension)

    @staticmethod
    def create_vector_store(
        settings: ExperienceSettings,
        data_dir: Path,
        embedding_dim: int,
    ) -> VectorStore:
        backend = (settings.vector_store.backend or settings.vector_store_backend).lower()
        sqlite_path = settings.vector_store.sqlite_path or settings.vector_store_sqlite_path
        q_host = settings.vector_store.qdrant_host or settings.vector_store_qdrant_host
        q_port = settings.vector_store.qdrant_port or settings.vector_store_qdrant_port
        q_coll = (
            settings.vector_store.qdrant_collection
            or settings.vector_store_qdrant_collection
        )
        q_key = settings.vector_store.qdrant_api_key or settings.vector_store_qdrant_api_key
        q_grpc = settings.vector_store.qdrant_prefer_grpc or settings.vector_store_qdrant_prefer_grpc
        if backend == "qdrant":
            store = QdrantVectorStore(
                host=q_host,
                port=q_port,
                collection=q_coll,
                dimension=embedding_dim,
                api_key=q_key,
                prefer_grpc=q_grpc,
            )
            if store.is_available:
                return store
            if not settings.fallback_on_error:
                raise RuntimeError("qdrant vector store unavailable")
            log.warning("fallback to sqlite vector store")

        db_path = data_dir / sqlite_path
        return SQLiteVectorStore(ExperienceSQLiteStore(db_path))

    @staticmethod
    def create_graph_store(settings: ExperienceSettings, data_dir: Path) -> GraphStore:
        backend = (settings.graph_store.backend or settings.graph_store_backend).lower()
        sqlite_path = settings.graph_store.sqlite_path or settings.graph_store_sqlite_path
        n_uri = settings.graph_store.neo4j_uri or settings.graph_store_neo4j_uri
        n_user = settings.graph_store.neo4j_user or settings.graph_store_neo4j_user
        n_pass = settings.graph_store.neo4j_password or settings.graph_store_neo4j_password
        n_db = settings.graph_store.neo4j_database or settings.graph_store_neo4j_database
        if backend == "neo4j":
            store = Neo4jGraphStore(
                uri=n_uri,
                user=n_user,
                password=n_pass,
                database=n_db,
            )
            if store.is_available:
                return store
            if not settings.fallback_on_error:
                raise RuntimeError("neo4j graph store unavailable")
            log.warning("fallback to sqlite graph store")

        db_path = data_dir / sqlite_path
        return SQLiteGraphStore(ExperienceSQLiteStore(db_path))
