# OpenEvo

**简体中文:** [README.zh.md](README.zh.md)

<p align="center">
  <img width="1376" height="768" alt="Clipboard - 2026-04-23 14 54 40" src="https://github.com/user-attachments/assets/b0bb0b3e-2548-4f38-9f6a-09df97dbd154" />
</p>

**OpenEvo** delivers **memory**, **closed-loop learning**, and **structured notes (Notes/Wiki)** as a self-contained, deployable service, with an HTTP and plugin model plus bundled **Claude Code** and **OpenClaw** examples so the chat pipeline can read and write context automatically—no manual tool invocation on every turn.

**Brand assets** (web, docs, favicon): see [docs/BRANDING.md](docs/BRANDING.md). Repository paths: `../assets/openevo-logo-wordmark.png` (wordmark) and `../assets/openevo-logo.png` (icon).

## Install

```bash
cd openevo
pip install -e .
```

## Run the API

```bash
evo serve
# default http://127.0.0.1:8765
```

Optional environment variables:

- `OPENEVO_DATA_DIR` — data directory (defaults to `.openevo` under the project)
- `OPENEVO_HOST` / `OPENEVO_PORT` — bind address
- **Logging** (Pydantic nested): `OPENEVO_LOG__LEVEL` (`DEBUG` / `INFO` / …), `OPENEVO_LOG__FORMAT` (`json` or `text`), `OPENEVO_LOG__FILE` (optional file sink)

## API documentation

After startup:

- Swagger UI: `http://127.0.0.1:8765/docs`
- ReDoc: `http://127.0.0.1:8765/redoc`
- OpenAPI JSON: `/openapi.json`

## Configuration and hot reload

You may place `config.json`, `config.yaml`, or `config.yml` in the data directory; they are **deep-merged** with built-in defaults. At runtime, **watchdog** watches these files and refreshes the values returned by `get_settings()`.

> **Note:** Hot reload mainly affects options read through `get_settings()`. Service objects already created in the app `lifespan` (e.g. `MemoryService`, `LearningService`, `WikiStore`) are not rebuilt automatically. Restart the process if you need a full rewire to new settings.

## Core capabilities

| Module | Description |
|--------|-------------|
| Memory | Two-bucket curated memory (`memory` / `user`) plus an episodic JSON API for plugins |
| Learning | `observations.jsonl` → instinct JSON → skill drafts under `evolved/` |
| Notes | Local Markdown wiki with SQLite-backed search |

## HTTP overview

- `GET /health`
- `POST /api/v1/memories/group` — batch episodic writes for plugins
- `POST /api/v1/memories/search` — episodic search
- `POST /api/v1/memories/curated` — curated memory `add` \| `remove` \| `replace`
- `GET /api/v1/learning/cycle?dry_run=false` — autonomous learning loop
- `GET /api/v1/notes/orient` — wiki orientation
- `POST /api/v1/notes/query` — wiki query

### Open Experience Space (OES)

Arbitrary data is shaped into **experiences** through **connectors** and stored in `<data_dir>/experience/experience.db` (vectors, metadata, and graph edges). The default is a lightweight deterministic text embedding with no extra model dependencies. Relevant settings include `OPENEVO_EXPERIENCE__ENABLED` (default `true`) and `OPENEVO_EXPERIENCE__EMBEDDING_DIM` (default `128`).

Pluggable backends (with automatic fallback so the rest of the stack keeps working):

- **Vector store:** `OPENEVO_EXPERIENCE__VECTOR_STORE__BACKEND=sqlite|qdrant`
- **Graph store:** `OPENEVO_EXPERIENCE__GRAPH_STORE__BACKEND=sqlite|neo4j`
- **Embeddings:** `OPENEVO_EXPERIENCE__EMBEDDING__PROVIDER=hash|sentence_transformer`
- If a remote dependency is missing and `OPENEVO_EXPERIENCE__FALLBACK_ON_ERROR=true`, the service falls back to SQLite + `HashEmbedding`

| Prefix | Description |
|--------|-------------|
| `POST /api/v1/experience/ingest` | Ingest experience; optional `adapter`: `code` / `chat` / `error` / `doc` / `tool` |
| `POST /api/v1/experience/query` | Semantic search (`vector` / `graph` / `hybrid`) |
| `POST /api/v1/experience/compose` | Compose multiple experiences |
| `POST /api/v1/experience/graph/*` | Edges, causal reasoning, policy-chain search |
| `POST /api/v1/agents/*` | Register agents, shared experience, sessions, voting |
| `POST /api/v1/market/*` | Listings, trades, evaluation, population-level strategy evolution |

## CLI

```bash
evo status
evo learn --dry-run
```

## Plugins

- **Claude Code:** `plugins/claude-code-plugin/` (Node 18+; `hooks.json` calls `.mjs` entrypoints)
- **OpenClaw:** `plugins/openclaw-plugin/` (`registerContextEngine`, `assemble` / `afterTurn`)

One-shot install (requires `bash`; probes `OPENEVO_BASE_URL` for `/health` unless `SKIP_HEALTH_CHECK=1`):

```bash
bash scripts/install-plugins.sh
```

- **Claude Code:** `plugins/claude-code-plugin/install.sh` (copies into `~/.claude/plugins/openevo-memory`, writes `.env.openevo`)
- **OpenClaw:** `plugins/openclaw-plugin/install.mjs` (registers the plugin path in `~/.openclaw/openclaw.json`)

Plugins use `OPENEVO_BASE_URL` to point at this service.

## Further documentation

- [OpenEvo product page](../openos/index.html#docs) — static landing (Chinese / English; in-page README summary)
- [Architecture](docs/ARCHITECTURE.md)
- [Plugin guide](docs/PLUGIN_GUIDE.md)
- [Branding & logos](docs/BRANDING.md)

## License

MIT
