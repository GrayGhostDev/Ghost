# CURSOR.md — Ghost Backend (Level 2 Shared Framework)

For AI-consumable rules, see `.cursor/rules/`.

## Runtime Identity

| Key | Value |
|---|---|
| API port | `8801` |
| DB port | `127.0.0.1:5433` (loopback only) |
| Redis port | `127.0.0.1:6380` (loopback only) |
| Container prefix | `ghost-be-*` |
| Networks | `ghost-backend-net` + `ggdc-shared-net` |
| Language | Python 3.12 / FastAPI |
| GitHub | `GrayGhostDev/Ghost.git` |

## Module Structure

```
src/ghost/
├── config.py      — Configuration (env, YAML, JSON, GCP SM overlay)
├── database.py    — SQLAlchemy async with psycopg v3
├── auth.py        — JWT + bcrypt + RBAC
├── api.py         — FastAPI integration + middleware
├── logging.py     — Structured logging (Loguru)
├── models.py      — Base models + repository pattern
├── tasks.py       — Background task processing
├── storage.py     — File upload management
├── email.py       — SMTP/provider support
├── websocket.py   — WebSocket support
└── utils.py       — Utility functions
```

## Authentication Scope

- This Level 2 framework does **not** use Clerk session/UI authentication directly.
- Clerk implementation details are owned by Level 3 app repositories.

## Proxyman MCP Boundary

- Proxyman MCP is managed globally (`~/.cursor/mcp.json`, `~/.mcp.json`), not in this repo-local `.cursor/mcp.json`.
- Local proxy settings are optional debugging aids and must not be required for staging/production behavior.
- Canonical governance: `~/Business/docs/proxyman/PROXYMAN_GUIDE.md` and `~/Business/docs/integrations/MCP_TOPOLOGY.md`.

## Development Commands

```bash
docker compose up -d                   # Start full stack
docker compose logs -f backend         # Tail API logs
curl http://localhost:8801/health      # Health check

# Database
make db/start && make db/create        # Local PostgreSQL
alembic upgrade head                   # Run migrations

# Testing
pytest                                 # All tests
pytest --cov=src/ghost                 # With coverage
```

## Database Driver

Uses **psycopg v3** (not psycopg2). `migrations/env.py` converts `postgresql://` to `postgresql+psycopg://`.

## GCP Authentication

| Environment | Auth Method |
|---|---|
| Docker Compose | `.env` file |
| Minikube | ADC mount + K8s Secrets |
| Cloud Run | GCP Secret Manager native |

Set `GCP_SECRET_PROJECT=grayghostdata-system` for Secret Manager overlay.
