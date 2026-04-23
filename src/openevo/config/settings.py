from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("openevo.config.settings")

_settings_version: list[int] = [0]


class MemorySettings(BaseModel):
    memory_char_limit: int = 2200
    user_char_limit: int = 1375
    governance_enabled: bool = True
    default_score: float = 0.5
    legacy_score: float = 0.4
    score_min: float = 0.0
    score_max: float = 1.0


class LearningSettings(BaseModel):
    min_tool_uses_for_instinct: int = 2
    min_failures_for_instinct: int = 2
    max_instincts_per_learn: int = 10
    evolve_min_instincts: int = 3
    evolve_cluster_threshold: int = 2


class NotesSettings(BaseModel):
    enabled: bool = True
    path: str = "~/openevo-wiki"
    auto_orient: bool = True


class LogSettings(BaseModel):
    level: str = "INFO"
    format: str = "json"  # json | text
    file: str | None = None


class ExperienceSettings(BaseModel):
    """Open Experience Space (OES) settings with pluggable backends."""

    enabled: bool = True
    embedding_dim: int = 128  # backward compatible default
    fallback_on_error: bool = True

    vector_store_backend: str = "sqlite"  # sqlite | qdrant
    vector_store_sqlite_path: str = "experience/experience.db"
    vector_store_qdrant_host: str = "localhost"
    vector_store_qdrant_port: int = 6333
    vector_store_qdrant_collection: str = "openevo_experiences"
    vector_store_qdrant_api_key: str | None = None
    vector_store_qdrant_prefer_grpc: bool = False

    graph_store_backend: str = "sqlite"  # sqlite | neo4j
    graph_store_sqlite_path: str = "experience/experience.db"
    graph_store_neo4j_uri: str = "bolt://localhost:7687"
    graph_store_neo4j_user: str = "neo4j"
    graph_store_neo4j_password: str = "neo4j"
    graph_store_neo4j_database: str = "neo4j"

    embedding_provider: str = "hash"  # hash | sentence_transformer
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    embedding_normalize: bool = True
    vector_store: VectorStoreSettings = Field(default_factory=lambda: VectorStoreSettings())
    graph_store: GraphStoreSettings = Field(default_factory=lambda: GraphStoreSettings())
    embedding: EmbeddingSettings = Field(default_factory=lambda: EmbeddingSettings())


class VectorStoreSettings(BaseModel):
    backend: str = "sqlite"  # sqlite | qdrant
    sqlite_path: str = "experience/experience.db"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "openevo_experiences"
    qdrant_api_key: str | None = None
    qdrant_prefer_grpc: bool = False


class GraphStoreSettings(BaseModel):
    backend: str = "sqlite"  # sqlite | neo4j
    sqlite_path: str = "experience/experience.db"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"
    neo4j_database: str = "neo4j"


class EmbeddingSettings(BaseModel):
    provider: str = "hash"  # hash | sentence_transformer
    dimension: int = 128
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    device: str = "cpu"
    normalize: bool = True


ExperienceSettings.model_rebuild()


class OpenEvoConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENEVO_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    data_dir: str = Field(default=".openevo", description="Relative to cwd or absolute")
    host: str = "127.0.0.1"
    port: int = 8765
    memory: MemorySettings = Field(default_factory=MemorySettings)
    learning: LearningSettings = Field(default_factory=LearningSettings)
    notes: NotesSettings = Field(default_factory=NotesSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    experience: ExperienceSettings = Field(default_factory=ExperienceSettings)

    def resolve_data_dir(self) -> Path:
        p = Path(os.path.expandvars(os.path.expanduser(self.data_dir)))
        if not p.is_absolute():
            p = Path.cwd() / p
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()


def deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def load_openevo_config() -> OpenEvoConfig:
    """Env-first settings, merged with ``<data_dir>/config.{json,yaml}`` if present."""
    env_cfg = OpenEvoConfig()
    data_root = env_cfg.resolve_data_dir()
    for name in ("config.json", "config.yaml", "config.yml"):
        cfg_file = data_root / name
        if not cfg_file.exists():
            continue
        try:
            if name.endswith(".json"):
                patch = json.loads(cfg_file.read_text(encoding="utf-8"))
            else:
                try:
                    import yaml
                except ImportError:
                    log.warning("pyyaml missing; skip %s", cfg_file)
                    continue
                patch = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
            if not isinstance(patch, dict):
                continue
            merged = deep_merge_dict(env_cfg.model_dump(), patch)
            return OpenEvoConfig.model_validate(merged)
        except Exception as e:
            log.exception("failed loading %s: %s", cfg_file, e)
            return env_cfg
    return env_cfg


@lru_cache(maxsize=64)
def _cached_settings(version: int) -> OpenEvoConfig:
    return load_openevo_config()


def get_settings() -> OpenEvoConfig:
    return _cached_settings(_settings_version[0])


def reload_settings() -> None:
    """Invalidate settings cache (e.g. after ``config.json`` change)."""
    _settings_version[0] += 1


def clear_settings_cache() -> None:
    """Testing: clear LRU and bump version so env monkeypatch applies."""
    _cached_settings.cache_clear()
    _settings_version[0] += 1
