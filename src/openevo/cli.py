from __future__ import annotations

import json

import typer
import uvicorn

from openevo.config.settings import get_settings
from openevo.core.learning import LearningService
from openevo.core.logging_config import setup_logging
from openevo.core.memory import MemoryService
from openevo.core.notes import WikiStore

app = typer.Typer(help="OpenEvo — memory, learning, notes")


@app.callback()
def _configure_logging() -> None:
    cfg = get_settings()
    setup_logging(
        level=cfg.log.level,
        json_format=cfg.log.format == "json",
        log_file=cfg.log.file,
    )


@app.command()
def serve(
    host: str | None = typer.Option(None, help="Bind host"),
    port: int | None = typer.Option(None, help="Port"),
) -> None:
    """Run HTTP API server."""
    cfg = get_settings()
    h = host or cfg.host
    p = port or cfg.port
    uvicorn.run(
        "openevo.api.server:app",
        host=h,
        port=p,
        factory=False,
        reload=False,
    )


@app.command()
def learn(dry_run: bool = typer.Option(False, "--dry-run", help="Evolve dry run")) -> None:
    """Run one learning + evolve cycle."""
    svc = LearningService()
    rep = svc.run_autonomous_cycle(dry_run=dry_run)
    typer.echo(json.dumps(rep.__dict__, ensure_ascii=False, indent=2))


@app.command()
def status() -> None:
    """Show data dirs and quick stats."""
    cfg = get_settings()
    root = cfg.resolve_data_dir()
    mem = MemoryService(root, cfg)
    wiki = WikiStore(cfg=cfg)
    typer.echo(f"data_dir: {root}")
    typer.echo(f"notes_root: {wiki.root} exists={wiki.exists()}")
    m, u = mem.render_prompt_blocks()
    typer.echo(f"curated_memory_blocks: bool(memory)={bool(m)} bool(user)={bool(u)}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()

# Typer CLI entry for setuptools
def run() -> None:
    app()


# Some installers expect `app` to be the Typer object
__all__ = ["app", "main", "run"]
