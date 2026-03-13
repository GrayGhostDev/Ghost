# Database Architecture — Ghost Backend

## Overview

Ghost Backend uses its own PostgreSQL instance, separate from client project databases.
Client projects (SP001, SmileDental, Nomics, DBU) use Supabase independently — there is no sync between them.

## Topology

```
┌─────────────────────────────────────────────────────────────┐
│  Environment         │  Host              │  Port  │ Driver │
├──────────────────────┼────────────────────┼────────┼────────┤
│  Local dev (MacPorts)│  localhost          │  5432  │ psycopg│
│  Docker Compose      │  postgres (internal)│  5432  │ psycopg│
│  Docker from host    │  127.0.0.1          │  5433  │ psycopg│
│  Minikube (K8s)      │  localhost (fwd)    │  5433  │ psycopg│
│  Cloud Run           │  Cloud SQL (GCP SM) │  5432  │ psycopg│
└──────────────────────┴────────────────────┴────────┴────────┘
```

### Local Development (MacPorts PostgreSQL 16)

Direct connection to a locally-installed PostgreSQL instance.

```
App (uvicorn) ──→ localhost:5432 ──→ MacPorts PostgreSQL 16
```

- Install: `make db/install && make db/init && make db/start && make db/create`
- Credentials stored in macOS Keychain (see `make env/keychain-setup`)
- `DATABASE_URL=postgresql://ghost:password@localhost:5432/ghost_db`

### Docker Compose

Backend container connects to the `postgres` service on the internal `ghost-backend-net` network.

```
ghost-be-api ──→ postgres:5432 ──→ ghost-be-db (container)
                                    ↕
                           host: 127.0.0.1:5433 (loopback only)
```

- Internal: `postgresql://postgres:ghost_password@postgres:5432/ghost`
- From host: `postgresql://postgres:ghost_password@localhost:5433/ghost`
- Redis: internal `redis:6379`, host `127.0.0.1:6380`

### Minikube (Kubernetes)

StatefulSet with port-forwarding to reuse the same host ports as Docker Compose.

```
App Pod ──→ postgres-svc:5432 ──→ PostgreSQL StatefulSet
                                    ↕
                           port-forward: localhost:5433
```

- Start: `make mk/start && make sk/dev`
- Port-forward: API `localhost:8801`, DB `localhost:5433`, Redis `localhost:6380`
- GCP auth: `make mk/gcp-mount` (mounts ADC credentials into minikube)

### Cloud Run (Production)

Cloud Run connects to Cloud SQL via GCP Secret Manager overlay.

```
Cloud Run ──→ Cloud SQL (via unix socket or private IP)
               ↕
         GCP Secret Manager provides DATABASE_URL
```

- Set `GCP_SECRET_PROJECT=sylvan-flight-476922-m7` to enable secret overlay
- `config.py` fetches secrets from GCP SM only for fields that are empty/default
- Env vars always take precedence over GCP SM values

## Driver: psycopg v3

All environments use **psycopg v3** (`psycopg[binary]`), not psycopg2.

Both `database.py` and `migrations/env.py` convert `postgresql://` → `postgresql+psycopg://`
so that SQLAlchemy uses the psycopg v3 dialect. This ensures consistent behavior across
local dev, Docker, K8s, and Cloud Run.

If you see `ModuleNotFoundError: No module named 'psycopg2'`, your DATABASE_URL is being
passed without the driver conversion. Check that you're going through `database.py` or
`migrations/env.py` and not constructing an engine directly.

## Migrations (Alembic)

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply all pending
alembic upgrade head

# Rollback one
alembic downgrade -1

# Show current version
alembic current
```

Alembic connects using the same `get_database_url()` function that converts the driver.
Migrations run automatically on container startup unless `SKIP_MIGRATIONS=true`.

## Connection Pooling

| Setting | Default | Notes |
|---------|---------|-------|
| pool_size | 10 | Concurrent connections |
| max_overflow | 20 | Burst capacity |
| pool_timeout | 30s | Wait for connection |
| pool_recycle | 3600s | Reconnect interval |

## Monitoring

- **PostgreSQL Exporter**: `127.0.0.1:9187` → Prometheus scrape
- **Redis Exporter**: `127.0.0.1:9188` → Prometheus scrape
- **Grafana Dashboard**: `localhost:3201` (Level 2)

## Client Project Databases

Client projects use Supabase — they do NOT share Ghost Backend's PostgreSQL:

| Project | Database | Supabase Ref |
|---------|----------|--------------|
| SP001 | Supabase (hosted) | — |
| SmileDental | Supabase (hosted) | vlddfeaudmzburebseyo |
| Nomics | Supabase (hosted) | gioimmhfqniosduezxam |
| DBU | Supabase (hosted) | — |
