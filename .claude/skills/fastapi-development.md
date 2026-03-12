# Ghost Backend FastAPI Development

## When to use
When developing or modifying the Ghost Backend API service — Gunicorn configuration, async PostgreSQL patterns, Redis session management, and health endpoints.

## Key facts
- **Service:** Ghost Backend API
- **Port:** 8801 (host) → 8801 (container)
- **Database:** PostgreSQL on port 5433
- **Cache:** Redis on port 6380
- **Framework:** FastAPI with Gunicorn/Uvicorn workers
- **Network:** ghost-be-net + ggdc-shared-net

## Project structure
```
ghost-backend/
├── docker-compose.yml       # Service definitions (API, PostgreSQL, Redis)
├── Dockerfile               # Multi-stage build
├── requirements.txt         # Python dependencies
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Pydantic BaseSettings
│   ├── routes/              # API route handlers
│   ├── services/            # Business logic
│   ├── models/              # Pydantic models
│   └── middleware/          # Custom middleware
├── gunicorn.conf.py         # Gunicorn configuration
├── tests/                   # Test suite
└── migrations/              # Database migrations
```

## Gunicorn configuration
```python
# gunicorn.conf.py
bind = "0.0.0.0:8801"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
accesslog = "-"
errorlog = "-"
loglevel = "info"
```

## Database connection patterns
```python
# Async PostgreSQL with asyncpg
import asyncpg

_pool: asyncpg.Pool | None = None

async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host="localhost",
            port=5433,
            user="postgres",
            database="ghost_backend",
            min_size=5,
            max_size=20,
        )
    return _pool

async def query(sql: str, *args) -> list[dict]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        return [dict(row) for row in rows]
```

## Redis session management
```python
import redis.asyncio as aioredis

_redis: aioredis.Redis | None = None

async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            "redis://localhost:6380",
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis

# Session operations
async def create_session(user_id: str, data: dict, ttl: int = 3600) -> str:
    r = await get_redis()
    session_id = secrets.token_urlsafe(32)
    await r.set(f"session:{session_id}", json.dumps({"user_id": user_id, **data}), ex=ttl)
    return session_id
```

## Health endpoint pattern
```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health endpoint for monitoring and load balancer checks."""
    checks = {}

    # Database health
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"

    # Redis health
    try:
        r = await get_redis()
        await r.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {e}"

    all_healthy = all(v == "healthy" for v in checks.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
    }
```

## Docker Compose patterns
```yaml
services:
  api:
    build: .
    ports:
      - "127.0.0.1:8801:8801"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    labels:
      com.ggdc.project: "ghost-backend"
      com.ggdc.service: "api"
      com.ggdc.level: "2"
      com.ggdc.scrape: "true"
      com.ggdc.metrics_port: "8801"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8801/health"]
      interval: 15s
      timeout: 5s
      retries: 3
```

## Commands
```bash
# Start ghost-backend stack
cd ~/Business/GGDC-System/ghost-backend && docker compose up -d

# View logs
docker compose logs -f api

# Check health
curl -sf http://localhost:8801/health | jq

# Database access
psql -h localhost -p 5433 -U postgres ghost_backend

# Redis access
redis-cli -p 6380

# Run tests
pytest tests/
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| API won't start | Check PostgreSQL is healthy first (`pg_isready -p 5433`) |
| Connection pool exhausted | Increase `max_size` or check for connection leaks |
| Redis timeout | Check Redis container health, verify port 6380 |
| Gunicorn workers crash | Check for memory leaks, increase `--timeout` |
| Health check fails | Check database and Redis connectivity |
