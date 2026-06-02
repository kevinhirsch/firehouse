# Deployment

Firehouse ships as a Docker Compose stack (the app plus ChromaDB, SearXNG, and
ntfy) and also runs natively on Linux, macOS, and Windows. After install,
configure models/search/email inside **Settings** — only edit `.env` for
deployment-level overrides (see [Configuration](configuration.md)).

On first boot Firehouse creates an admin account (`admin` unless
`FIREHOUSE_ADMIN_USER` is set) and prints a temporary password. For Docker, find
it with `docker compose logs firehouse | grep -i password`. Log in, then change
it in **Settings**.

## Docker (recommended)

```bash
git clone https://github.com/kevinhirsch/firehouse.git
cd firehouse
cp .env.example .env       # optional but recommended
docker compose up -d --build
```

Open `http://localhost:7000` (or `http://<host-ip>:7000` from another machine)
once the containers are healthy.

## Native Linux / macOS

```bash
git clone https://github.com/kevinhirsch/firehouse.git
cd firehouse
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup.py
python -m uvicorn app:app --host 127.0.0.1 --port 7000
```

Requirements: Python 3.11+. Cookbook background downloads also need `tmux`. Use
`--host 0.0.0.0` only when you intentionally want LAN/reverse-proxy access.

### Apple Silicon

Docker on macOS can't use the Metal GPU. For GPU-accelerated Cookbook on an
M-series Mac, run natively:

```bash
git clone https://github.com/kevinhirsch/firehouse.git
cd firehouse
./start-macos.sh           # installs Homebrew deps, venv, setup; starts on :7860
./build-macos-app.sh       # optional: clickable .app + .dmg
```

It launches on port `7860` (AirPlay often holds `7000`) and uses
llama.cpp/Ollama for Metal. vLLM/SGLang are CUDA/ROCm-only; MLX-only models are
not served.

## Native Windows

One-command launcher (creates the venv, installs deps, runs setup, starts the
server; safe to re-run):

```powershell
git clone https://github.com/kevinhirsch/firehouse.git
cd firehouse
powershell -ExecutionPolicy Bypass -File .\launch-windows.ps1
```

The core app runs fully native. For Cookbook background downloads and the agent
shell tool, also install [Git for Windows](https://git-scm.com/download/win)
(provides `bash.exe`). Local GPU *serving* of vLLM/SGLang needs Linux/WSL2; for a
local model on Windows, [Ollama](https://ollama.com/download) is easiest — point
Firehouse at `http://localhost:11434/v1` in **Settings**.

## Proxmox

Proxmox doesn't run the app directly — give it a Linux guest and run the Docker
stack inside.

- **VM (simplest; required for GPU passthrough):** create an Ubuntu 22.04/24.04
  or Debian 12 VM (≥4 GB RAM, ≥20 GB disk), then:
  ```bash
  curl -fsSL https://get.docker.com | sh
  git clone https://github.com/kevinhirsch/firehouse.git && cd firehouse
  cp .env.example .env
  docker compose up -d --build
  ```
- **LXC container (lighter):** use a Debian/Ubuntu container, but it must be
  **privileged** (or have nesting + keyctl enabled) for Docker to run inside.
  On the Proxmox host, add to `/etc/pve/lxc/<id>.conf`:
  ```
  features: nesting=1,keyctl=1
  ```
  then run the same Docker steps inside the container.

## Networking & ports

The Firehouse container serves on `0.0.0.0:7000` internally. What it's published
on at the host is controlled by Compose variables (read by `docker-compose.yml`,
not by the Python app):

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_BIND` | `0.0.0.0` | Host interface the web UI is published on. Set `127.0.0.1` to restrict to loopback. |
| `APP_PORT` | `7000` | Host port for the web UI. |
| `CHROMADB_BIND` | `127.0.0.1` | Host bind for the bundled ChromaDB (`:8100`). |
| `NTFY_BIND` | `127.0.0.1` | Host bind for the bundled ntfy (`:8091`). |
| `NTFY_BASE_URL` | `http://localhost:8091` | Public base URL for ntfy push links. |
| `OLLAMA_BIND` | `127.0.0.1` | Host bind for the bundled Ollama service (`:11434`), when the `docker/ollama.yml` overlay is enabled. |

The web UI binds to `0.0.0.0` by default, so it's reachable across the host's
network from the start. The bundled services (ChromaDB, SearXNG, ntfy) stay on
`127.0.0.1` and aren't exposed to your LAN unless you opt in.

> Exposing the UI on `0.0.0.0` means anyone who can route to the host can reach
> it. Keep `AUTH_ENABLED=true` and put it behind HTTPS (below) on untrusted
> networks.

## GPU overlays (Docker)

Install the host GPU runtime first, then add **one** overlay to `.env`:

```bash
# NVIDIA (needs nvidia-container-toolkit + `nvidia-ctk runtime configure --runtime=docker`)
COMPOSE_FILE=docker-compose.yml:docker/gpu.nvidia.yml

# AMD ROCm (needs ROCm drivers + the render group's GID)
COMPOSE_FILE=docker-compose.yml:docker/gpu.amd.yml
RENDER_GID=992
```

Verify:

```bash
docker compose exec firehouse nvidia-smi -L
docker compose exec firehouse rocm-smi
```

The overlays only expose the GPU devices. The slim image still needs CUDA/ROCm
userspace installed via **Cookbook → Dependencies** (vLLM, llama-cpp-python, …)
before models serve on GPU.

## Ollama (local models)

There are three ways to run Ollama with Firehouse, from least to most hands-on.

### Option A — bundled Docker service (no host install, no config)

Run Ollama as a managed Compose service. Firehouse auto-wires to it and you
manage models entirely from the UI. Add the overlay to `.env`:

```bash
COMPOSE_FILE=docker-compose.yml:docker/ollama.yml
# with GPU, append a GPU overlay too:
# COMPOSE_FILE=docker-compose.yml:docker/ollama.yml:docker/gpu.nvidia.yml
```

Then `docker compose up -d`. Ollama joins the compose network; Firehouse reaches
it at `http://ollama:11434/v1` automatically (no Settings edit needed), and the
port is published on `127.0.0.1:11434` so host tools can reach it too (override
with `OLLAMA_BIND`). Models persist in the `ollama-data` volume.

### Option B — host install, one command

If you'd rather run Ollama on the host (e.g. to use the host GPU directly):

```bash
sudo ./scripts/firehouse-ollama-setup            # or: ... qwen2.5
```

It installs Ollama, sets `OLLAMA_HOST=0.0.0.0:11434` via a systemd drop-in so the
container can reach it, pulls a model, points `.env` at the host endpoint,
restarts Firehouse, and verifies connectivity.

### Option C — fully manual

Run Ollama with `OLLAMA_HOST=0.0.0.0:11434`, then add the endpoint
`http://host.docker.internal:11434/v1` under **Settings → model endpoints**
(or click the **Ollama** / **Scan for Servers** buttons there to auto-fill it).

### Managing local models — in the UI

Once Ollama is reachable, open **Settings → model endpoints → Local models** to
install, list, and remove models point-and-click (pull progress streams live).
Models you install appear in the chat model picker automatically.

### Managing local models — CLI (optional)

The same operations are scriptable. The wrapper targets the same Ollama your
`.env` points at:

```bash
./scripts/firehouse-models list            # installed models
./scripts/firehouse-models pull qwen2.5    # install / update a model
./scripts/firehouse-models running         # models loaded in memory
./scripts/firehouse-models remove llama3.1 # uninstall
./scripts/firehouse-models info llama3.1   # model details
./scripts/firehouse-models endpoint        # show which Ollama it targets
```

## Updating

```bash
./scripts/firehouse-update            # backup data, pull code + images, rebuild & restart
```

`firehouse-update` snapshots `data/`, runs `git pull`, pulls the latest service
images, then rebuilds and recreates the containers. Your `data/` and `.env` are
left in place; SQLite schema migrations run automatically on startup. Pass
`--no-backup` to skip the snapshot. If any step fails it aborts **before** the
restart, so a bad pull never leaves a half-updated stack.

Updating whatever branch you're on, so make sure the host is on `main`
(`git checkout main`) for mainline updates.

## Backups

```bash
./scripts/firehouse-backup snapshot                 # → backups/YYYY-MM-DD-HHMMSS.tar.gz
./scripts/firehouse-backup snapshot --out /mnt/nas/firehouse.tgz
./scripts/firehouse-backup list
./scripts/firehouse-backup verify PATH
./scripts/firehouse-backup restore PATH --yes       # destructive: overwrites data/
```

The snapshot tarballs the entire `data/` directory, using `sqlite3 .backup` for
a consistent copy of the database while the app keeps running. Restore is
destructive and requires `--yes`.

## Putting it behind HTTPS

Firehouse serves plain HTTP. That's fine for `localhost` and trusted LAN/VPN
use, but browsers warn on the login page and credentials travel in cleartext.
For anything reachable beyond your machine, terminate TLS at a reverse proxy.

Shortest path with [Caddy](https://caddyserver.com/) (auto Let's Encrypt):

```caddy
firehouse.example.com {
  reverse_proxy localhost:7000
}
```

nginx/Traefik are equivalent — proxy `localhost:7000` and terminate TLS at the
proxy. When serving over HTTPS, also set `SECURE_COOKIES=true` and restrict
`ALLOWED_ORIGINS` to your real origin. See [SECURITY.md](../SECURITY.md) for the
full hardening checklist.

## Built-in MCP servers (optional)

Firehouse auto-registers a few built-in MCP servers at startup. The npx-based
ones (currently the browser server, `@playwright/mcp`) only start when their
package is already in the local npx cache; otherwise they're skipped with a log
message rather than blocking startup. To enable the browser MCP (navigation,
screenshots, vision), run once and restart:

```bash
npx -y @playwright/mcp@latest --version    # installs ~300 MB (Playwright)
```

## Useful checks

```bash
docker compose ps
docker compose logs --tail=120 firehouse
docker compose logs firehouse | grep -E 'ChromaDB|MemoryVectorStore|DEGRADED'
```

More fixes in [Troubleshooting](troubleshooting.md).
