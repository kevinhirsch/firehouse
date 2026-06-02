# Firehouse Documentation

Guides for installing, configuring, operating, and extending Firehouse — the
self-hosted AI workspace.

## Contents

| Guide | What it covers |
|-------|----------------|
| [Architecture](architecture.md) | How the app is structured: entry point, request flow, subsystems, data storage, background work, and the auth model. |
| [Configuration](configuration.md) | Complete environment-variable reference and the `.env` workflow. |
| [Deployment](deployment.md) | Docker, native Linux/macOS, Windows, Proxmox, GPU overlays, Ollama, updating, backups, and putting it behind HTTPS. |
| [API Reference](api.md) | The HTTP API: conventions, authentication, streaming, and an endpoint inventory grouped by feature. |
| [Troubleshooting](troubleshooting.md) | Fixes for the issues people hit most: connection refused, binding, Ollama, ChromaDB, ports, and logs. |

## Other documents

- [README](../README.md) — project overview and quick start.
- [CONTRIBUTING](../CONTRIBUTING.md) — development setup, tests, and pull-request guidelines.
- [SECURITY](../SECURITY.md) — security policy and hardening checklist.
- [ROADMAP](../ROADMAP.md) — what's planned and where help is wanted.
- [ACKNOWLEDGMENTS](../ACKNOWLEDGMENTS.md) — upstream projects and licenses.

> The source code is the ultimate source of truth. These guides are written to
> match the current `main`; if something drifts, trust the code and please open
> a PR to fix the docs.
