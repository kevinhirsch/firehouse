# Configuration

Most of Firehouse is configured **inside the app** — run `/setup` on first boot
or open **Settings** to add model providers, search, email, calendar, and so on.
Those values are stored in the database, not in environment variables.

Use `.env` only for **deployment-level defaults and secrets you want present
before the first boot** — bind address, port, auth toggles, the database URL, or
a pre-seeded admin password.

## The `.env` workflow

```bash
cp .env.example .env     # start from the documented template
# edit .env
docker compose up -d     # Compose reads .env automatically
```

For a native (non-Docker) run, export the variables in your shell or process
manager before launching `uvicorn`. `.env` is gitignored — never commit real
secrets.

Notes on the tables below:

- **“—”** in the Default column means unset/empty.
- Values shown are the code defaults. **Docker Compose overrides some of them**
  (noted inline) so the bundled services can talk to each other on the compose
  network.
- Booleans accept `true`/`false` (and `1`/`0` where noted).

---

## LLM & models

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_HOST` | `localhost` | Primary LLM host used for model discovery. |
| `LLM_HOSTS` | — | Comma-separated additional hosts to scan for models (common serve ports, including Ollama's `11434`). |
| `OLLAMA_BASE_URL` | — | Explicit Ollama OpenAI-compatible base URL, e.g. `http://host.docker.internal:11434/v1`. In Docker this is the usual way to reach host Ollama. |
| `OLLAMA_URL` | — | Alternate variable for the Ollama base URL (`OLLAMA_BASE_URL` takes precedence). |
| `OPENAI_API_KEY` | — | OpenAI API key. Prefer adding providers in **Settings** unless you need it pre-seeded. |
| `RESEARCH_LLM_ENDPOINT` | — | Override the chat-completions endpoint used by Deep Research. |

## Embeddings & RAG

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_URL` | — | OpenAI-compatible embeddings endpoint (`/v1/embeddings`). Defaults to `http://{LLM_HOST}:11434/v1/embeddings`. |
| `EMBEDDING_MODEL` | — | Embedding model name served at `EMBEDDING_URL` (e.g. `all-minilm:l6-v2`). |
| `FASTEMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local fallback embedding model (fastembed/ONNX) used when no HTTP embedding API is available. Downloads (~50 MB) on first use. |
| `FASTEMBED_CACHE_PATH` | `~/.cache/fastembed` | Where fastembed caches its model. |
| `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` | — | Hugging Face token for gated model/embedding downloads. |
| `HF_HUB_DOWNLOAD_MAX_WORKERS` | `8` | Parallel workers for Hugging Face downloads. |

## Vector store (ChromaDB)

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMADB_HOST` | `localhost` | ChromaDB host. **Docker Compose overrides to `chromadb`.** |
| `CHROMADB_PORT` | `8100` | ChromaDB port for manual host runs. **Docker Compose overrides to `8000`** (in-network). |
| `CHROMADB_CONNECT_TIMEOUT` | `2.0` | Seconds to wait when connecting before falling back to keyword search. |

## Search & web

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARXNG_INSTANCE` | `http://localhost:8080` | SearXNG base URL. **Docker Compose overrides to `http://searxng:8080`.** |
| `SEARXNG_GENERAL_ENGINES` | `bing,mojeek,presearch` | Engines used for general SearXNG queries. |
| `SEARXNG_SECRET` | generated on first Docker boot | Optional SearXNG cookie/CSRF secret. Leave blank unless you need to pin it. |
| `TAVILY_API_KEY` | — | Enables the Tavily search provider. |
| `SERPER_API_KEY` | — | Enables the Serper (Google) search provider. |
| `GOOGLE_API_KEY` | — | Google Programmable Search Engine key. |
| `GOOGLE_PSE_CX` | — | Google Programmable Search Engine CX id. |
| `DATA_BRAVE_API_KEY` | — | Brave Search API key. |

## Database & storage

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLAlchemy database URL. |
| `DATA_DIR` | `data` | Base directory for all on-disk state. |
| `FIREHOUSE_MAIL_ATTACHMENTS_DIR` | `{DATA_DIR}/mail-attachments` | Where extracted email attachments are written. |
| `FIREHOUSE_PERSONAL_UPLOAD_MAX_BYTES` | `26214400` (25 MB) | Max size for a personal-docs upload. |

## Auth & security

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_ENABLED` | `true` | Require login. Keep `true` for any network-accessible deployment. |
| `LOCALHOST_BYPASS` | `false` | **Development only.** Skip auth for loopback requests. Never enable for Docker, LAN, reverse-proxy, or shared use. |
| `SECURE_COOKIES` | `false` | Mark session cookies `Secure` (set `true` when serving over HTTPS). |
| `ALLOWED_ORIGINS` | `http://localhost,http://127.0.0.1` | CORS allow-list. Restrict to your real origin in production. |
| `FIREHOUSE_ADMIN_USER` | `admin` | Username for the auto-created first admin. |
| `FIREHOUSE_ADMIN_PASSWORD` | — | Pre-seed the first admin password at setup instead of using the generated one. |
| `FIREHOUSE_INTERNAL_TOKEN` | generated | Shared secret for the agent's loopback tool calls to internal routes. |
| `FIREHOUSE_FALLBACK_OWNER` | `owner@localhost` | Owner id assigned to data created when auth is disabled. |
| `FIREHOUSE_SINGLE_USER` | `1` | Single-user mode (skips multi-user gating where applicable). |

> Networking note: `APP_BIND`, `APP_PORT`, and the bundled-service binds
> (`CHROMADB_BIND`, `NTFY_BIND`, …) are **Docker Compose** settings, not read by
> the Python app directly. They're documented in
> [Deployment → Networking & ports](deployment.md#networking--ports).

## Email (IMAP / SMTP)

Per-account credentials are normally entered in **Settings** and stored
encrypted in the database. These variables provide defaults/fallbacks, mainly
for single-account or scripted setups.

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAP_HOST` | — | IMAP server hostname. |
| `IMAP_PORT` | `993` | IMAP port. |
| `IMAP_USER` | — | IMAP username. |
| `IMAP_PASSWORD` | — | IMAP password. |
| `IMAP_SSL` | `false` | Use implicit SSL for IMAP. |
| `IMAP_STARTTLS` | `true` | Use STARTTLS for IMAP. |
| `SMTP_HOST` | — | SMTP server hostname. |
| `SMTP_PORT` | `465` | SMTP port. |
| `SMTP_USER` | — | SMTP username. |
| `SMTP_PASSWORD` | — | SMTP password. |
| `SMTP_SSL` | `true` | Use implicit SSL for SMTP. |
| `SMTP_STARTTLS` | `false` | Use STARTTLS for SMTP. |
| `EMAIL_FROM` | — | Default From address. |
| `EMAIL_SOCKET_TIMEOUT` | `20` | IMAP/SMTP socket timeout (seconds). |
| `ARCHIVE_FOLDER` | `Archive` | IMAP folder used when archiving. |
| `TRASH_FOLDER` | `Trash` | IMAP folder used when deleting. |

## Contacts (CardDAV)

| Variable | Default | Description |
|----------|---------|-------------|
| `CARDDAV_URL` | — | CardDAV server URL. |
| `CARDDAV_USERNAME` | — | CardDAV username. |
| `CARDDAV_PASSWORD` | — | CardDAV password. |

## Background tasks & scheduling

| Variable | Default | Description |
|----------|---------|-------------|
| `FIREHOUSE_INPROCESS_TASKS` | `1` | Run the scheduled-task runner in-process. Set `0` to drive tasks from an external runner. |
| `FIREHOUSE_INPROCESS_POLLERS` | `1` | Run email pollers in-process. Set `0` if you poll via cron/systemd (`scripts/firehouse-mail poll-*`) to avoid two schedulers racing on SQLite. |
| `FIREHOUSE_SCRIPT_HOST` | `localhost` | Host for the `run_script` task action. Empty/`local`/`localhost` runs on the app host; an SSH alias runs scripts remotely. |
| `CLEANUP_ENABLED` | `True` | Enable periodic cleanup of old uploads/temp data. |
| `CLEANUP_INTERVAL_HOURS` | `24` | Cleanup interval. |

## MCP, runtime & misc

| Variable | Default | Description |
|----------|---------|-------------|
| `FIREHOUSE_DISABLE_MCP` | — | Set (to any non-empty value) to skip starting built-in MCP servers. |
| `LOG_LEVEL` | `WARNING` | Python logging level (`DEBUG`, `INFO`, `WARNING`, …). |
| `REQUEST_HARD_TIMEOUT` | `45` | Seconds before non-streaming requests are aborted. Streaming routes are exempt. |
| `FIREHOUSE_SKIP_RUN_HINT` | — | Suppress the “now run …” hint that `setup.py` prints. |

## Demo / testing only

Used by the demo-email seeding scripts; not needed for normal installs.

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_ALLOW_WIPE` | — | Allow the demo seeder to wipe demo data. |
| `DEMO_IMAP_HOST` | `localhost` | Demo IMAP host. |
| `DEMO_IMAP_PORT` | `31143` | Demo IMAP port. |
| `DEMO_IMAP_USER` | `demo@firehouse.local` | Demo IMAP user. |
| `DEMO_IMAP_PASSWORD` | `demodemo` | Demo IMAP password. |

---

See also: [Deployment](deployment.md) for Compose-level settings (`APP_BIND`,
`APP_PORT`, GPU overlays) and [Architecture](architecture.md) for how these
subsystems fit together.
