# Plugin guide
This guide explains how to connect **Claude Code** and **OpenClaw** to an OpenEvo server so memory, wiki search, and episodic writes work end-to-end. It expands on the short notes in the main README with **paths, env vars, hook lifecycles, and verification** taken from the current `plugins/` tree.

---

## 1. Prerequisites (all integrations)

1. **Run the API** — from the `openevo` package: `evo serve` (or `uvicorn` with the same `openevo.api.server:app` import). Default listen address is `http://127.0.0.1:8765` unless you override `OPENEVO_HOST` / `OPENEVO_PORT` in settings.
2. **Point clients at the server** — set:

   ```bash
   export OPENEVO_BASE_URL="http://127.0.0.1:8765"
   ```

   All official plugins read **`OPENEVO_BASE_URL`** (and the Node clients fall back to that default if unset).
3. **Health check** — `GET /health` should return `{"status":"healthy",...}`. The bundled installer uses this unless you set `SKIP_HEALTH_CHECK=1`.

---

## 2. One-shot install (Claude + OpenClaw)

From the **repository root** (or any path that contains `openevo/scripts/`):

```bash
export OPENEVO_BASE_URL="http://127.0.0.1:8765"   # optional override
bash openevo/scripts/install-plugins.sh
```

Behavior:

- Probes `OPENEVO_BASE_URL/health` when `curl` is available and `SKIP_HEALTH_CHECK` is not `1`.
- Runs `plugins/claude-code-plugin/install.sh` (Bash).
- Runs `plugins/openclaw-plugin/install.mjs` (Node).

This is the fastest way to get both plugin trees registered on a dev machine.

---

## 3. Claude Code plugin

### 3.1 Layout and runtime

- **Source** lives under `openevo/plugins/claude-code-plugin/`.
- **Node.js** v18+ is required (hooks are `.mjs` executed by `node`).
- `hooks/hooks.json` registers **command** hooks for these lifecycle events:

| Event | Script | Role (typical) |
|-------|--------|----------------|
| `SessionStart` | `session-context.mjs` | Load / seed session context from OpenEvo. |
| `UserPromptSubmit` | `inject-memories.mjs` | Inject curated / relevant memory into the prompt path. |
| `Stop` | `store-memories.mjs` | Persist conversation slices to OpenEvo. |
| `SessionEnd` | `session-summary.mjs` | Summarize or flush session to OpenEvo. |

`CLAUDE_PLUGIN_ROOT` is supplied by the host so paths resolve to the **installed** plugin directory.

### 3.2 Manual or scripted install

**Scripted** (`install.sh`):

- Copies `hooks/` and `plugin.json` into `~/.claude/plugins/openevo-memory` (or `CLAUDE_CONFIG_DIR` if you use a non-default Claude config root).
- Writes `~/.claude/plugins/openevo-memory/.env.openevo` with `OPENEVO_BASE_URL` and `OPENEVO_USER_ID` (default `claude-code-user`).
- If `claude` CLI is on `PATH`, attempts `claude plugin install` on that folder; otherwise you register the folder via the **Claude Code plugin UI**.

**Manual**: point Claude Code’s plugin root at `plugins/claude-code-plugin` (or the copied tree under `~/.claude/plugins/openevo-memory`).

### 3.3 Payload and schema drift

Claude’s hook **stdin JSON** shape can evolve. If a hook script’s `readStdinJson()` paths no longer match the payload, **adjust the field paths** in the relevant `hooks/scripts/*.mjs` to match the live payload (defensive parsing + logging is recommended when debugging).

---

## 4. OpenClaw plugin

### 4.1 Registration

- **Manifest**: `plugins/openclaw-plugin/openclaw.plugin.json` — `kind: "context-engine"`, entry `index.js`.
- **Default export** calls `api.registerContextEngine("openevo-context", factory)` and builds the engine in `src/engine.js`.

**Install script** (`install.mjs`):

- Merges this plugin’s directory into `~/.openclaw/openclaw.json` under `plugins.load.paths` (creates the file if needed).
- After install, **restart the OpenClaw gateway** (e.g. `openclaw gateway restart` as printed by the script).

### 4.2 Context engine behavior

`src/engine.js` implements:

- **`assemble({ messages, prompt })`**  
  - Builds a short text query from `prompt` or the latest user message.  
  - Calls OpenEvo **`POST /api/v1/memories/search`** (with `filters.group_id`) and **`POST /api/v1/notes/query`**.  
  - If anything is found, returns `systemPromptAddition` with “OpenEvo memories” and “Wiki hits” sections (and `estimatedTokens` for budgeting).

- **`afterTurn({ messages, prePromptMessageCount })`**  
  - Slices new user/assistant messages since the last save, maps them to the API shape, and **`POST /api/v1/memories/group`** to append episodic rows for the configured `user_id` / `group_id`.

### 4.3 Config: `userId` and `groupId`

In the OpenClaw plugin config object, set:

- **`userId`** — defaults to `openclaw-user` if omitted.  
- **`groupId`** — defaults to `openclaw-default` if omitted.

These **partition** episodic memory and search filters so multiple clients or projects do not overwrite each other’s `group_id` buckets.

### 4.4 Base URL in Node

`src/client.js` resolves the API base as:

`process.env.OPENEVO_BASE_URL` → `http://127.0.0.1:8765`

Set the env var in the **same environment** that starts the OpenClaw gateway or your process manager if the API is not on localhost.

---

## 5. Verification (acceptance)

Run these after plugins are connected and the server is up.

| Step | What to do | Expected |
|------|------------|----------|
| Episodic round-trip | `POST /api/v1/memories/group` with a test `group_id` / `messages`, then `POST /api/v1/memories/search` with the same `group_id` in `filters` | Search returns the newly written snippets (or related rows). |
| Wiki | Create/init the wiki root (per Notes settings), then `GET /api/v1/notes/orient` | Non-empty `stats` (or documented orient payload) once the wiki is initialized. |
| Health | `GET /health` | `200` and healthy JSON. |

For OpenClaw, watch logs for ``[openevo-context] afterTurn saved`` after a turn; for Claude, confirm hooks run without timeout errors in the IDE hook log.

---

## 6. Troubleshooting

| Symptom | What to check |
|--------|----------------|
| Installer warns about health | Start `evo serve` first, or set `SKIP_HEALTH_CHECK=1` to force continue. |
| 404 / connection refused on plugins | `OPENEVO_BASE_URL` must include scheme/host/port; no trailing slash required for the bundled clients, but the server must be reachable from the same machine (or use LAN URL + firewall rules). |
| OpenClaw sees no context | Ensure gateway restarted after `install.mjs`; check `userId` / `groupId` and that `assemble` query length is not always empty. |
| Claude hook timeouts | Increase `timeout` in `hooks.json` (seconds) for heavy I/O, or ensure OpenEvo responds within SLA. |
| CORS / browser | Plugins use server-side `fetch` or `node` — browser CORS usually N/A; if you call the API from a web app, the server’s CORS is currently permissive but tighten in production. |

---

## 7. Security and production

- Use **HTTPS** and place OpenEvo **behind** authentication at the edge when exposed beyond localhost.  
- Treat **`OPENEVO_BASE_URL` as a secret** in shared CI logs only if the URL or tokenized path is sensitive.  
- The API is **not** authenticated in the stock plugin clients — lock down the network (VPN, mTLS, or an API gateway) in production.

---

## 8. See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — how `MemoryService`, routes, and `app.state` fit together.  
- [README.md](../README.md) — install and quick API overview.
