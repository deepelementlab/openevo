# OpenEvo

**English:** [README.md](README.md)

<p align="center">
  <img width="1376" height="768" alt="Clipboard - 2026-04-23 14 54 40" src="https://github.com/user-attachments/assets/b14445ff-95f7-485c-9749-65cfb3adab9e" />
</p>

**OpenEvo** 将 **记忆（Memory）**、**闭环学习（Learning）** 与 **结构化笔记（Notes/Wiki）** 以可独立部署的服务交付；以 HTTP API 与可扩展的插件为产品边界，并随仓库提供 **Claude Code hooks** 与 **OpenClaw context-engine** 等配套示例，在对话管线中自动完成写入与检索，无需在聊天中反复显式指定工具。

## 安装

```bash
cd openevo
pip install -e .
```

## 启动 API

```bash
evo serve
# 默认 http://127.0.0.1:8765
```

环境变量（可选）：

- `OPENEVO_DATA_DIR`：数据目录（默认项目下 `.openevo`）
- `OPENEVO_HOST` / `OPENEVO_PORT`：绑定地址
- **日志**（Pydantic nested）：`OPENEVO_LOG__LEVEL`（`DEBUG`/`INFO`/…）、`OPENEVO_LOG__FORMAT`（`json` 或 `text`）、`OPENEVO_LOG__FILE`（可选，写入文件）

## API 文档

启动后访问：

- Swagger UI：`http://127.0.0.1:8765/docs`
- ReDoc：`http://127.0.0.1:8765/redoc`
- OpenAPI JSON：`/openapi.json`

## 配置与热重载

在数据目录下可放置 `config.json`、`config.yaml` 或 `config.yml`，会与默认设置**深度合并**。服务运行时会用 **watchdog** 监听这些文件的变更并刷新 `get_settings()` 读到的配置。

> **注意**：热重载主要影响通过 `get_settings()` 读取的选项；已在 `lifespan` 中创建的 `MemoryService` / `LearningService` / `WikiStore` 等实例不会自动重建，若需完全按新配置重建服务，请重启进程。

## 核心能力

| 模块 | 说明 |
|------|------|
| Memory | 双桶精编记忆（`memory`/`user`）+ 插件用 episodic JSON API |
| Learning | `observations.jsonl` → 本能 JSON → `evolved/` 技能草稿 |
| Notes | 本地 Markdown Wiki + SQLite 索引检索 |

## HTTP 摘要

- `GET /health`
- `POST /api/v1/memories/group` — 插件批量写入对话片段
- `POST /api/v1/memories/search` — 检索 episodic
- `POST /api/v1/memories/curated` — 精编记忆 `add|remove|replace`
- `GET /api/v1/learning/cycle?dry_run=false` — 自主闭环
- `GET /api/v1/notes/orient` — Wiki 导向信息
- `POST /api/v1/notes/query` — Wiki 查询

### 开放经验空间（OES）

万物数据经 **连接器** 规范为经验，写入 `<data_dir>/experience/experience.db`（向量 + 元数据 + 关系边）。默认使用轻量确定性文本嵌入（无额外模型依赖）。环境变量：`OPENEVO_EXPERIENCE__ENABLED`（默认 `true`）、`OPENEVO_EXPERIENCE__EMBEDDING_DIM`（默认 `128`）。

可插拔后端（自动降级，不影响正常使用）：

- **向量**：`OPENEVO_EXPERIENCE__VECTOR_STORE__BACKEND=sqlite|qdrant`
- **图谱**：`OPENEVO_EXPERIENCE__GRAPH_STORE__BACKEND=sqlite|neo4j`
- **嵌入**：`OPENEVO_EXPERIENCE__EMBEDDING__PROVIDER=hash|sentence_transformer`
- 若外部依赖不可用且 `OPENEVO_EXPERIENCE__FALLBACK_ON_ERROR=true`，自动回退到 SQLite + HashEmbedding

| 前缀 | 说明 |
|------|------|
| `POST /api/v1/experience/ingest` | 摄入经验；可选 `adapter`: `code` / `chat` / `error` / `doc` / `tool` |
| `POST /api/v1/experience/query` | 语义检索（`vector` / `graph` / `hybrid`） |
| `POST /api/v1/experience/compose` | 多经验合成 |
| `POST /api/v1/experience/graph/*` | 建边、因果推断、策略链搜索 |
| `POST /api/v1/agents/*` | 注册 Agent、共享经验、协作会话与表决 |
| `POST /api/v1/market/*` | 挂牌、交易、评估、群体策略进化 |

## CLI

```bash
evo status
evo learn --dry-run
```

## 插件

- **Claude Code**：`plugins/claude-code-plugin/`（Node 18+，`hooks.json` 调用 `.mjs`）
- **OpenClaw**：`plugins/openclaw-plugin/`（`registerContextEngine`，`assemble` / `afterTurn`）

一键安装（需 bash；会先探测 `OPENEVO_BASE_URL` 上的 `/health`，可设 `SKIP_HEALTH_CHECK=1` 跳过）：

```bash
bash scripts/install-plugins.sh
```

- **Claude Code**：`plugins/claude-code-plugin/install.sh`（复制到 `~/.claude/plugins/openevo-memory`，写入 `.env.openevo`）
- **OpenClaw**：`plugins/openclaw-plugin/install.mjs`（向 `~/.openclaw/openclaw.json` 注册插件路径）

插件通过环境变量 `OPENEVO_BASE_URL` 指向本服务。

## 文档

- [OpenEvo 产品展示主页](../openos/index.html#docs)（对外介绍，静态页，中/英切换；站内置 README 要点板块）
- [架构说明](docs/ARCHITECTURE.md)
- [插件指南](docs/PLUGIN_GUIDE.md)
- [品牌与 Logo](docs/BRANDING.md)

## 许可

GPL-3.0 license.
