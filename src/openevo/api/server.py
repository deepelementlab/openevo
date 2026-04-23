from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from openevo.api import (
    agent_routes,
    experience_routes,
    learning_routes,
    market_routes,
    memory_routes,
    notes_routes,
)
from openevo.config.settings import get_settings, reload_settings
from openevo.config.watcher import DataDirConfigWatcher
from openevo.core.agent_coordination import AgentCoordinationProtocol
from openevo.core.evolution_market import EvolutionMarket
from openevo.core.experience_space import ExperienceSpace
from openevo.core.learning import LearningService
from openevo.core.logging_config import setup_logging
from openevo.core.memory import MemoryService
from openevo.core.notes import WikiStore

logger = logging.getLogger("openevo.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    setup_logging(
        level=cfg.log.level,
        json_format=cfg.log.format == "json",
        log_file=cfg.log.file,
    )
    data_dir = cfg.resolve_data_dir()
    watcher = DataDirConfigWatcher(data_dir, reload_settings)
    watcher.start()
    app.state.config_watcher = watcher

    app.state.memory = MemoryService(data_dir, cfg)
    app.state.learning = LearningService(cfg)
    app.state.wiki = WikiStore(cfg=cfg)
    if cfg.experience.enabled:
        app.state.experience_space = ExperienceSpace(data_dir, cfg)
        app.state.agent_coord = AgentCoordinationProtocol(app.state.experience_space)
        app.state.evolution_market = EvolutionMarket(app.state.experience_space)
    else:
        app.state.experience_space = None
        app.state.agent_coord = None
        app.state.evolution_market = None
    logger.info(
        json.dumps(
            {
                "event": "startup",
                "data_dir": str(data_dir),
                "hot_reload": getattr(watcher, "_observer", None) is not None,
            }
        )
    )
    yield
    watcher.stop()
    logger.info(json.dumps({"event": "shutdown"}))


def create_app() -> FastAPI:
    app = FastAPI(
        title="OpenEvo API",
        version="0.1.0",
        description="Memory, closed-loop learning, and structured notes for agent plugins (Claude Code / OpenClaw).",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())[:12]
        start = time.perf_counter()
        logger.info(
            json.dumps(
                {
                    "event": "request_start",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                }
            )
        )
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "event": "request_end",
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                }
            )
        )
        response.headers["X-Request-Id"] = request_id
        return response

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "openevo"}

    @app.get("/api/v1/prompt/snapshot", tags=["prompt"])
    def prompt_snapshot() -> dict[str, Any]:
        """Curated memory blocks + wiki orient for system prompt injection."""
        mem_svc: MemoryService = app.state.memory
        m, u = mem_svc.render_prompt_blocks()
        wiki: WikiStore = app.state.wiki
        cfg = get_settings()
        orient: dict[str, Any] = {}
        if cfg.notes.enabled and wiki.exists():
            orient = wiki.get_orient_payload(20)
        return {"memory_block": m, "user_block": u, "wiki_orient": orient}

    app.include_router(memory_routes.router)
    app.include_router(learning_routes.router)
    app.include_router(notes_routes.router)
    app.include_router(experience_routes.router)
    app.include_router(agent_routes.router)
    app.include_router(market_routes.router)
    return app


app = create_app()
