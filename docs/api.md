# API Reference

Firehouse exposes a JSON/SSE HTTP API — about **396 endpoints across ~40
routers**. The front end is just a client of this API, so anything the UI does
is scriptable. This page documents the conventions and inventories the surface
by feature area.

> The route definitions in `routes/*.py` are the source of truth. This reference
> is organized by router; full paths are shown including each router's prefix.

## Conventions

**Base URL.** Everything is served from the app origin, e.g.
`http://localhost:7000`. API paths live under `/api/...`.

**Authentication.** Two mechanisms, checked by the auth middleware:

- **Session cookie** — set by `POST /api/auth/login`; used by the browser.
- **Bearer token** — `Authorization: Bearer <token>` using an API token created
  at `POST /api/tokens`; used for programmatic access.

Most endpoints require auth. Public ones include `/`, the SPA deep links,
`/api/health`, `/api/version`, `/api/emoji/*`, and the `/api/auth/{setup,
signup, login, logout, status}` flow. Admin-only surfaces include `/api/admin/*`,
`/api/shell/*`, `/api/embeddings/*`, user management under `/api/auth/*`, MCP
management, webhooks, and model/cookbook serving.

**Ownership.** Sessions, documents, notes, gallery images, memories, etc. are
scoped to their owner; you only see and mutate your own.

**Streaming (SSE).** Long-running endpoints stream `text/event-stream`:
`POST /api/chat_stream`, `GET /api/chat/resume/{id}`, `POST /api/rewrite`,
`GET /api/research/stream/{id}`, `POST /api/shell/stream`,
`POST /api/model/download`, and `POST /api/cookbook/setup`.

**Errors.** Standard HTTP status codes with a JSON `{"detail": "..."}` body
(FastAPI's default). `401` = not authenticated, `403` = not permitted, `404` =
not found or not owned by you, `422` = validation error.

**Listing every route.** To dump the live routing table:

```bash
python -c "import app; [print(f'{sorted(r.methods)} {r.path}') for r in app.app.routes if hasattr(r,'methods')]"
```

## Endpoint inventory

### Auth & users — `/api/auth` (26)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/setup` | Create the initial admin (public). |
| POST | `/api/auth/signup` | Register a new user (when signup is enabled). |
| POST | `/api/auth/login` | Log in (password + optional 2FA). |
| POST | `/api/auth/logout` | Log out / revoke the session. |
| GET | `/api/auth/status` | Current auth status and user. |
| POST | `/api/auth/change-password` | Change your password. |
| POST | `/api/auth/2fa/setup` · `/2fa/confirm` · `/2fa/disable` | Manage TOTP 2FA. |
| GET | `/api/auth/2fa/status` | 2FA status. |
| GET/POST/PUT/DELETE | `/api/auth/users[...]` | Admin user management (list, create, rename, privileges, delete). |
| GET/POST | `/api/auth/features` · `/settings` | Read/update feature flags and app settings. |
| GET/POST/PUT/DELETE | `/api/auth/integrations[...]` | Manage provider integrations. |

### API tokens — `/api` (3)

`GET /api/tokens` · `POST /api/tokens` · `DELETE /api/tokens/{id}` — list, create,
and revoke bearer tokens.

### Chat — (8)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message (non-streaming). |
| POST | `/api/chat_stream` | Send a message, stream the reply (SSE). |
| GET | `/api/chat/resume/{session_id}` | Re-attach to an in-flight stream (SSE). |
| POST | `/api/chat/stop/{session_id}` | Stop an in-flight response. |
| GET | `/api/chat/stream_status/{session_id}` | Poll stream status. |
| POST | `/api/inject_context/{session_id}` | Inject context without a user turn. |
| GET | `/api/search` | Search across chat messages. |
| POST | `/api/rewrite` | Rewrite a message (SSE). |

### Sessions — `/api` (19)

List, create, rename, delete, archive/unarchive, bulk-delete, export, fork,
compact, mark-important, and auto-sort chat sessions
(`/api/sessions`, `/api/session/{id}[...]`, `/api/history/{id}`).

### History — (11)

Message-level operations on a session: get history, add/edit/delete messages,
truncate, fork, merge, mark-stopped, conversation topics
(`/api/session/{id}/...`, `/api/conversations/topics`).

### Memory — `/api/memory` (13)

Add, search, list (timeline), pin, update, delete, import, audit, and
auto-extract memories, plus relevance debugging
(`/api/memory/...`, `/api/memory/{id}`).

### Research — (15)

Start, stream (SSE), status, cancel, result/peek, report, library, detail,
archive, delete, spinoff, and image hide/unhide for Deep Research
(`/api/research/...`).

### Models & endpoints — `/api` (19)

List models, discover/probe/ping endpoints, manage model endpoints (create,
test, toggle, delete, list models, dependents), default chat model, and the tool
allow-list (`/api/models`, `/api/model-endpoints[...]`, `/api/discover`,
`/api/providers`, `/api/tools`).

### Documents — (23)

Create, read, update, patch, delete, version (list/get/restore), import PDF,
export PDF/zip, render pages/PNG, AI tidy, and AI-fill annotations
(`/api/document[s][...]`).

### Notes — `/api/notes` (10)

Get/update/delete notes, pin, archive, reorder, toggle checklist items, and fire
reminders (`/api/notes/...`).

### Tasks (scheduler) — `/api/tasks` (22)

Get/update/delete tasks, pause/resume, run/stop now, revert, list runs,
notifications, onboarding, metadata (actions/events/output targets), parse, and
per-task webhook trigger/regenerate (`/api/tasks/...`).

### Assistant — `/api/assistant` (6)

Personal-assistant session, settings, run/status of check-ins, and available
timezones (`/api/assistant/...`).

### Email — `/api/email` (41)

Full IMAP/SMTP surface: list/search/read, attachments (list/download/as-doc),
read/unread/archive/delete/move/flag, folders, compose uploads, scheduled sends,
send/draft, AI summarize/reply, writing-style extraction, urgency state,
contacts resolution, and multi-account management (`/api/email/...`).

### Calendar — `/api/calendar` (15)

CalDAV config/test/sync, list/create/update/delete calendars and events, ICS
import/export, and quick natural-language event parsing (`/api/calendar/...`).

### Contacts — `/api/contacts` (10)

CardDAV-backed list/search/add/edit/delete, VCF import/export, config, and clear
(`/api/contacts/...`).

### Gallery & image tools — (32)

Upload/replace/rename/rotate/delete images, albums (CRUD + add/remove),
favorites, tags (AI tag, batch, clear, dedupe), stats, zip download, and
local image operations: inpaint, harmonize, sharpen, denoise, upscale, remove
background, enhance face (`/api/gallery/...`, `/api/image/...`,
`/api/generated-image/{filename}`).

### Skills — `/api/skills` (18)

Index, built-in skills (get/override/reset), custom skills (add/get/update/
delete/markdown/test), search, and bulk audit (`/api/skills/...`).

### Cookbook (model serving) — (12)

SSH key, model download (SSE) and cached list, serve model, server setup (SSE),
GPU list, kill PID, state get/save, HF latest, and task status
(`/api/cookbook/...`, `/api/model/...`).

### Shell — (4)

Admin-only command execution and package management: `POST /api/shell/exec`,
`POST /api/shell/stream` (SSE), `GET /api/cookbook/packages`,
`POST /api/cookbook/packages/install`.

### Hardware fit — `/api/hwfit` (3)

`GET /api/hwfit/system` · `/models` · `/image-models` — system specs and
fit-scored model recommendations.

### Compare — `/api/compare` (5)

Start a blind A/B comparison, vote, record, list history, delete
(`/api/compare/...`).

### Search — (4)

`GET /api/search/config` · `GET /api/search/providers` · `POST /api/search` ·
`POST /api/search/query` — web search via the configured provider.

### Personal docs (RAG) — `/api/personal` (6)

Reload index, add/remove directory, upload, and delete files for personal-doc
retrieval (`/api/personal/...`).

### Embeddings — `/api/embeddings` (7, admin)

List/download/delete embedding models, check status, and get/set/clear the
embedding endpoint (`/api/embeddings/...`).

### MCP — `/api/mcp` (11)

List/add/toggle/delete MCP servers, reconnect, list tools (all/per-server),
per-tool enable/disable, and the OAuth authorize/callback/exchange flow
(`/api/mcp/...`).

### Webhooks — `/api` (6)

List/create/test/toggle/delete webhooks (admin) and the public token-triggered
`POST /api/v1/chat` (`/api/webhooks[...]`).

### Vault — `/api/vault` (6)

Encrypted secure storage: config, login, unlock, lock, logout
(`/api/vault/...`).

### TTS / STT — `/api/tts` (3) · `/api/stt` (2)

Synthesize text to speech (+ stats, cache clear) and transcribe audio (+ stats).

### Uploads — `/api/upload` (6)

Download an uploaded file, get/set its OCR/vision text, stats, and manual
cleanup (`/api/upload/...`).

### Presets — (8)

Get presets, custom preset, templates (list/save/delete), expand, and group
presets (`/api/presets[...]`).

### Smaller routers

| Router | Prefix | Routes | Endpoints |
|--------|--------|--------|-----------|
| Backup / import | — | 2 | `GET /api/export`, `POST /api/import` |
| Cleanup | `/api/cleanup` | 2 | preview + run cleanup |
| Diagnostics | — | 4 | `/api/db/stats`, `/api/rag/stats`, test routes |
| Editor drafts | — | 5 | CRUD for drawing-editor drafts |
| Signatures | — | 3 | list/create/delete signature stamps |
| Preferences | `/api/prefs` | 3 | get/set per-user prefs |
| Fonts | `/api/fonts` | 1 | list custom fonts |
| Emoji | `/api/emoji` | 1 | `GET /api/emoji/{code}.svg` (public) |
| Admin danger zone | `/api/admin` | 1 | `DELETE /api/admin/wipe/{kind}` (admin) |

### System & SPA (app.py)

`GET /` and deep links (`/login`, `/notes`, `/calendar`, `/cookbook`, `/email`,
`/memory`, `/gallery`, `/tasks`, `/library`) serve the SPA. `GET /api/health`,
`GET /api/version`, and `GET /api/runtime` report status and runtime config;
`/static/*` serves front-end assets.
