# Architecture

Firehouse is a single FastAPI application that serves both a static
single-page front end and a large JSON/SSE API. Business logic lives in plain
Python modules; persistence is SQLite plus a `data/` directory on disk, with an
optional ChromaDB vector store for semantic memory and document search.

```
Browser (static SPA)  ──HTTP/SSE──▶  FastAPI (app.py)
                                        │
                          middleware: CORS · security headers ·
                                       timeout · auth
                                        │
                                   routes/*.py            (HTTP layer)
                                        │
                              src/*.py · services/*       (business logic)
                                        │
                         core/ (ORM · auth · sessions)    (infrastructure)
                                        │
                    SQLite (data/app.db) · data/ files · ChromaDB
```

## Top-level layout

| Path | Responsibility |
|------|----------------|
| `app.py` | FastAPI entry point: builds the app, installs middleware, initializes singleton managers, and mounts ~40 routers. |
| `core/` | Infrastructure: SQLite ORM models (`database.py`), authentication (`auth.py`), session manager, request middleware, shared constants, atomic file I/O. |
| `src/` | Business logic: the agent loop, LLM client, tools/MCP, memory, RAG, deep research, task scheduler, document/image processing, encryption. |
| `routes/` | HTTP endpoint handlers, one module per feature area. Each exposes a `setup_*_routes(...)` factory that returns an `APIRouter`. |
| `services/` | Self-contained service packages: `memory`, `research`, `search`, `hwfit` (hardware fit), `tts`, `stt`, `shell`, `docs`. |
| `mcp_servers/` | Built-in [Model Context Protocol](https://modelcontextprotocol.io) servers (email, memory, image generation, RAG) that expose AI-callable tools. |
| `static/` | The front end: `index.html`, `login.html`, `landing.html`, `app.js`, and modular ES modules under `static/js/`. No build step. |
| `scripts/` | Operator CLIs (`firehouse`, `firehouse-mail`, `firehouse-backup`, `firehouse-update`, `firehouse-ollama-setup`, …) dispatched through `scripts/firehouse`. |
| `config/`, `docker/` | Compose/SearXNG config and the GPU compose overlays. |
| `tests/` | Pytest suite and a few JS checks. |

## Entry point and request flow

`app.py` builds the application in a fixed order:

1. **Create the app** and install middleware (outermost first):
   - `CORSMiddleware` — cross-origin policy from `ALLOWED_ORIGINS`.
   - Security headers — CSP nonce, `X-Frame-Options`, `Referrer-Policy`.
   - Request timeout — a hard cap (`REQUEST_HARD_TIMEOUT`, default 45s) that
     exempts long-lived streams like `/api/chat`, `/api/research`, and
     `/api/shell/stream`.
   - Auth — validates a session cookie or bearer token and stamps
     `request.state.current_user`. Supports an internal loopback token (used by
     the agent's own tool calls) and a development `LOCALHOST_BYPASS`.
2. **Mount static files** with revalidating cache headers so deploys don't serve
   stale JS/CSS.
3. **Initialize managers** — a set of singletons (session manager, memory
   manager, chat handler, research handler, RAG manager, task scheduler, TTS/STT
   services, MCP manager, …). Optional subsystems initialize lazily and degrade
   gracefully when their dependencies are missing.
4. **Include routers** — each `routes/*.py` factory is wired with the managers it
   needs.

A typical request flows:

```
HTTP request
  → CORS → security headers → timeout → auth middleware
  → routes/<feature>_routes.py handler
  → src/* or services/* business logic
  → core/database.py (SQLite) and/or data/ files
  → JSON, StreamingResponse (SSE), or FileResponse
```

For chat, the handler hands off to the streaming **agent loop**
(`src/agent_loop.py`), which iterates: call the model → parse tool blocks →
execute tools → feed results back → repeat until the model stops, persisting
messages through the session manager as it goes.

## Major subsystems

| Subsystem | Key modules |
|-----------|-------------|
| Chat / agent loop | `src/agent_loop.py`, `src/chat_handler.py`, `routes/chat_routes.py` |
| LLM client | `src/llm_core.py` (calls, streaming, host health, caching), `src/endpoint_resolver.py` (URL normalization), `src/model_context.py` (token budgeting) |
| Tools & MCP | `src/agent_tools.py`, `src/tool_implementations.py`, `src/mcp_manager.py`, `mcp_servers/` |
| Memory | `src/memory.py` (store), `src/memory_vector.py` (ChromaDB-backed semantic recall) |
| RAG (personal docs) | `src/rag_manager.py`, `src/rag_vector.py`, `src/rag_singleton.py` (lazy availability) |
| Deep research | `src/research_handler.py`, `src/deep_research.py`, `routes/research_routes.py` |
| Email | `routes/email_routes.py`, `routes/email_pollers.py`, `mcp_servers/email_server.py` |
| Calendar / contacts | `routes/calendar_routes.py`, `routes/contacts_routes.py` (CalDAV / CardDAV) |
| Cookbook (model serving) | `routes/cookbook_routes.py`, `services/hwfit/fit.py` (fit scoring), tmux-driven vLLM / llama.cpp / Ollama sessions |
| Task scheduler | `src/task_scheduler.py`, `src/event_bus.py`, `routes/task_routes.py` |
| Notes / tasks / documents | `routes/note_routes.py`, `routes/document_routes.py` |
| Gallery / images | `routes/gallery_routes.py`, `scripts/diffusion_server.py` |
| Search | `services/search/`, `routes/search_routes.py` |

## Data and storage

**SQLite** (`core/database.py`, default `sqlite:///./data/app.db`) holds the
relational state: chat sessions and messages, documents and their versions,
memories, email accounts (with encrypted credentials), gallery images and
albums, calendar calendars/events, scheduled tasks and their run history, notes,
MCP servers, API tokens, webhooks, and more. Lightweight schema changes are
applied automatically on startup by a chain of `_migrate_*` functions, so
upgrading in place is safe.

**The `data/` directory** holds everything else (all gitignored):

| Path | Contents |
|------|----------|
| `data/app.db` | The SQLite database. |
| `data/.app_key` | Fernet encryption key (created on first run, `0600`). |
| `data/auth.json` | Users, bcrypt password hashes, privileges, 2FA secrets. |
| `data/sessions.json` | Active session tokens and expiries. |
| `data/memory.json` | Memory entries (mirrored into the vector store when available). |
| `data/personal_docs/` | Files indexed for RAG. |
| `data/uploads/` | User uploads, organized by date. |
| `data/mail-attachments/` | Extracted email attachments. |
| `data/generated_images/` | Image-generation output. |
| `data/deep_research/` | Per-run research state. |
| `data/huggingface/`, `data/local/` | Cookbook model cache and installed serve engines (Docker). |

**ChromaDB** is optional. When reachable it powers semantic memory recall and
personal-document search; embeddings come from an OpenAI-compatible endpoint or
the local fastembed (ONNX) fallback. If ChromaDB is down, those features degrade
to keyword search instead of failing.

**Encryption** (`src/secret_storage.py`) uses Fernet to protect secrets such as
IMAP/SMTP passwords stored in the database. The key lives at `data/.app_key`.
This protects a stolen backup or disk image; it does not protect a live,
compromised process. Keep `data/` and the key off Git and off shared storage.

## Background work

- **Task scheduler** (`src/task_scheduler.py`) runs `ScheduledTask` rows on
  daily / weekly / monthly / once / cron schedules (timezone-aware), executing
  the agent loop and recording each run. Gated by `FIREHOUSE_INPROCESS_TASKS`.
- **Email pollers** (`routes/email_pollers.py`) poll IMAP for triage,
  summaries, and scheduled sends. Gated by `FIREHOUSE_INPROCESS_POLLERS` so you
  can drive polling from cron/systemd instead and avoid two schedulers racing on
  the same SQLite file.
- **Webhooks** (`src/webhook_manager.py`) fire on internal events and can be
  triggered externally via per-task tokens.
- **Cleanup** prunes old uploads/temp data on an interval
  (`CLEANUP_INTERVAL_HOURS`).

## Auth model

Authentication lives in `core/auth.py` with enforcement in the `app.py` auth
middleware:

- **Users** are stored in `data/auth.json` with bcrypt password hashes,
  optional TOTP 2FA, and a per-user **privilege** set (agent, browser, shell,
  documents, image generation, memory management, allowed models, daily message
  caps).
- **Sessions** are 256-bit tokens with a 7-day TTL, persisted in
  `data/sessions.json` and pruned on load. Changing a password revokes existing
  sessions.
- **API tokens** authenticate programmatic access via `Authorization: Bearer`
  and carry their own scopes.
- **Internal loopback token** lets the agent's own tools call admin routes over
  `127.0.0.1` as the synthetic `internal-tool` user.
- **Ownership**: sessions, documents, notes, gallery images, memories, etc.
  carry an `owner`, and routes filter by it. High-risk surfaces (shell, MCP
  management, API tokens, webhooks, model/cookbook serving, backup/vault, app
  settings) are admin-gated regardless of per-user privileges.

See the [Security policy](../SECURITY.md) for the hardening checklist that
follows from this model.
