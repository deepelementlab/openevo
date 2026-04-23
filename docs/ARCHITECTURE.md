# OpenEvo — System Architecture & Implementation (Simple)


## One-liner

**OpenEvo is a FastAPI service** that bundles **memory, closed-loop learning, wiki-style notes, and the Open Experience Space (OES)** in one process, with **SQLite as the default** and **optional Qdrant / Neo4j / sentence-transformers**, all behind a **single HTTP API** for tools and clients.

## Three layers

1. **API** (`openevo.api.*_routes`) — HTTP/JSON, middleware for logging and `X-Request-Id`.
2. **Domain** (`openevo.core.*`) — `MemoryService`, `LearningService`, `WikiStore`, `ExperienceSpace` (+ `ExperienceGraph`); code reads config via **`get_settings()`** only.
3. **Data** — local **SQLite** + **JSONL/files** under `learning/`; OES can use **remote** vector/graph stores and **falls back** to in-repo SQLite implementations when allowed.

**At startup**, `server` lifespan **constructs these services once** and stores them on **`app.state`**. **Editing** `config.json` / YAML **reloads** settings in `get_settings()`, but **does not recreate** long-lived service objects (restart for a full rewire).

## Main data path

**Plugins / clients** call Memory / Learning / Notes / Experience **REST** endpoints → writes go to **SQLite, files, or OES** → optional **`/api/v1/prompt/snapshot`** assembles **memory + wiki** snippets back into your **system prompt** stack.

## Important paths (under the data directory by default)

| Path | Role |
|------|------|
| `memory.sqlite3` | Curated + episodic |
| `learning/` | `observations.jsonl`, instincts, evolved output |
| `experience/` | Experience store (incl. default SQLite DB file) |
| Wiki root (default e.g. `~/openevo-wiki`) | Markdown tree + local index DB |

## Ops touchpoints

- `GET /health` — liveness and installer probes  
- Logs — **one JSON line per event** + request duration, easy to ship to your log stack

## Where to read more

- **Config & hot reload** — `config/settings.py`, `config/watcher.py`  
- **Pluggable OES** — `core/stores/factory.py`, `core/experience_space.py`  
