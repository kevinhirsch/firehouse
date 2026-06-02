# Troubleshooting

Fixes for the issues people hit most. Start by checking the containers and logs:

```bash
docker compose ps
docker compose logs --tail=120 firehouse
```

## "Connection refused" from another machine

A *refused* connection (as opposed to a *timeout*) almost always means the port
is bound to loopback, not that a firewall is dropping packets. Check what the app
is published on:

```bash
docker compose port firehouse 7000
#  127.0.0.1:7000  → loopback only (other machines can't reach it)
#  0.0.0.0:7000    → all interfaces (good)
```

If it shows `127.0.0.1`, set the host bind to all interfaces and recreate:

```bash
echo "APP_BIND=0.0.0.0" >> .env
docker compose up -d
```

Then bisect host-internal vs. network issues by testing locally first:

```bash
curl -sS -m 5 -o /dev/null -w "%{http_code}\n" http://localhost:7000
```

- A status code (200/302/401) → the app is fine; the problem is network/IP/
  firewall (below).
- Still refused → the app inside the container isn't listening yet; see
  [App not responding](#app-not-responding).

## Wrong IP or firewall

If `localhost:7000` works but `http://<ip>:7000` doesn't:

```bash
ip -4 addr | grep <your-ip>        # confirm the IP is actually this host
ufw status                         # Debian/Ubuntu firewall
firewall-cmd --list-all            # RHEL/Proxmox firewall
```

Allow the port if a firewall is active (`ufw allow 7000/tcp`). On Proxmox, also
check the datacenter/node/guest firewall rules for inbound TCP 7000.

## App not responding

If `curl http://localhost:7000` is refused on the host itself, the app inside
the container isn't up yet — it's still booting (uvicorn start, first-run setup)
or it crashed:

```bash
docker compose logs --tail=80 firehouse
```

Look for `Uvicorn running on http://0.0.0.0:7000` (healthy) versus a Python
traceback. Give first boot a minute; embedding/model downloads can delay
readiness.

## Port 7000 already in use

Something else holds the port (macOS AirPlay commonly uses 7000). Change it:

```bash
echo "APP_PORT=7001" >> .env
docker compose up -d
```

Then browse to `:7001`. For native runs, pass `--port 7001` to uvicorn.

## ChromaDB / memory shows "DEGRADED"

Memory and personal-doc search fall back to keyword matching when the vector
store is unreachable. Check:

```bash
docker compose ps chromadb
docker compose logs firehouse | grep -E 'ChromaDB|MemoryVectorStore|DEGRADED'
```

- In Docker, the app reaches ChromaDB at `chromadb:8000` (Compose sets this).
- For a manual run, set `CHROMADB_HOST`/`CHROMADB_PORT` to your ChromaDB.
- Raise `CHROMADB_CONNECT_TIMEOUT` if ChromaDB is slow to start.

The app keeps working without ChromaDB — you just lose semantic recall until
it's back.

## Ollama models don't appear

In Docker, the container reaches host Ollama via `host.docker.internal:11434`,
and Ollama must listen beyond loopback. Verify both sides:

```bash
curl -s http://localhost:11434/api/tags                                    # host can see Ollama
docker compose exec firehouse curl -s http://host.docker.internal:11434/api/tags   # container can too
```

If the second fails, Ollama is bound to loopback. The one-command fix sets
everything up:

```bash
sudo ./scripts/firehouse-ollama-setup
```

(or set `OLLAMA_HOST=0.0.0.0:11434` and restart Ollama). See
[Deployment → Ollama](deployment.md#ollama-local-models).

## Browser warns about an insecure password page

Firehouse serves plain HTTP. Browsers warn on the login page and credentials
travel in cleartext once you're off `localhost`. Put a TLS-terminating reverse
proxy in front and set `SECURE_COOKIES=true` — see
[Deployment → HTTPS](deployment.md#putting-it-behind-https).

## First-login password

On first boot a temporary admin password is printed. If you missed it:

```bash
docker compose logs firehouse | grep -i password
```

Log in, then change it in **Settings**. To pre-seed it instead, set
`FIREHOUSE_ADMIN_PASSWORD` before the first boot.

## Browser MCP / Playwright not starting

The browser MCP server only starts if `@playwright/mcp` is already cached. Enable
it once and restart:

```bash
npx -y @playwright/mcp@latest --version
```

## Reset to a clean state

Stop the stack and remove the data directory **(destructive — back up first)**:

```bash
./scripts/firehouse-backup snapshot     # keep a copy
docker compose down
rm -rf data/                            # wipes all users, chats, settings
docker compose up -d --build
```

## Still stuck?

Open an issue with your install method, OS, exact steps, and the relevant log
output — see [CONTRIBUTING.md](../CONTRIBUTING.md#issue-reports). Don't paste
secrets, tokens, or private logs.
