# Docker Compose Operations — Ghost Backend

## Service Topology

```
ghost-backend (compose project)
├── backend       (ghost-be-api)     — FastAPI app, port 8801
├── postgres      (ghost-be-db)      — PostgreSQL 16, port 127.0.0.1:5433
├── redis         (ghost-be-redis)   — Redis 7, port 127.0.0.1:6380
├── postgres-exporter (ghost-be-pg-exporter) — port 127.0.0.1:9187
└── redis-exporter    (ghost-be-redis-exporter) — port 127.0.0.1:9188→9121
```

## Network Membership

| Service | ghost-backend-net | ggdc-shared-net |
|---|---|---|
| backend | yes | yes |
| postgres | yes | no |
| redis | yes | no |
| postgres-exporter | yes | yes |
| redis-exporter | yes | yes |

Data services stay internal. Only the API and exporters join `ggdc-shared-net`.

## GGDC Label Requirements

Every service must have:
```yaml
labels:
  com.ggdc.project: "GGDC-System"
  com.ggdc.service: "<container-name>"
  com.ggdc.level: "2"
```

Metrics-exposing services add:
```yaml
  com.ggdc.scrape: "true"
  com.ggdc.metrics_port: "<port>"
```

## Port Binding Conventions

- **Always bind to 127.0.0.1** — never `0.0.0.0` for DB/Redis
- External access goes through Level 2 Traefik (`api.ghost.local`)
- All ports must be registered in `~/Business/config/port-registry.yaml`

## Dev vs Prod Differences

| Aspect | docker-compose.yml | docker-compose.prod.yml |
|---|---|---|
| Image | `ghost-backend:latest` | `ghost-backend:production` |
| Dockerfile | `Dockerfile` | `Dockerfile.prod` |
| Workers | 1 | 4 |
| Debug | true | false |
| Log level | INFO | WARNING |
| DB ports | Exposed (127.0.0.1:5433) | Internal only (`expose:`) |
| Volumes | Source mounted (hot reload) | Named volumes only |
| Resource limits | None | CPU/memory limits set |
| Restart | unless-stopped | always |

## Common Commands

```bash
# Start all services
docker compose up -d

# Start with rebuild
docker compose up -d --build

# Tail logs
docker compose logs -f backend

# Health check
curl http://localhost:8801/health

# Stop
docker compose down

# Production
docker compose -f docker-compose.prod.yml up -d
```

## Prerequisites

```bash
# Create shared network (once, from GGDC-System/)
cd ~/Business/GGDC-System && make networks

# Copy env file
cp .env.example .env
# Edit .env with actual secrets
```
