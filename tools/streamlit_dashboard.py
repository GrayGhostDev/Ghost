"""
Ghost Backend — Dev Admin Dashboard (Streamlit)

Dev-only dashboard for monitoring Ghost Backend services.
NOT for production — runs on the host via `make dashboard`.

IMPORTANT: Launch via `make dashboard` which strips Proxyman's PYTHONPATH
injection and proxy env vars. Running Streamlit directly will route all
HTTP calls through Proxyman, causing 404s on localhost endpoints.

Usage:
  make dashboard
"""

import os
import sys
import urllib.request
import urllib.parse
import json
from datetime import datetime
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Ghost Backend Dashboard",
    page_icon="👻",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Configuration — read from environment or .env file, with sane defaults
# ---------------------------------------------------------------------------


def _load_dotenv():
    """Load .env file from project root if it exists (simple key=value parser)."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Only set if not already in environment (env takes precedence)
        if key not in os.environ:
            os.environ[key] = value


_load_dotenv()

# The .env file contains Docker-internal values (DB_HOST=postgres, DB_PORT=5432)
# which don't work from the host. Use DASHBOARD_DB_* overrides, or fall back to
# host-mapped defaults. Only DB_PASSWORD/DB_NAME/DB_USER are safe to read from .env.
DB_HOST = os.environ.get("DASHBOARD_DB_HOST", "localhost")
DB_PORT = os.environ.get("DASHBOARD_DB_PORT", "5433")  # Host-mapped port
DB_NAME = os.environ.get("DB_NAME", "ghost")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "ghost_password")
API_PORT = os.environ.get("API_PORT", "8801")
REDIS_PORT = os.environ.get("DASHBOARD_REDIS_PORT", "6380")  # Host-mapped

API_URL = f"http://127.0.0.1:{API_PORT}"
PROMETHEUS_URL = "http://127.0.0.1:9091"
PG_EXPORTER_URL = "http://127.0.0.1:9187"
REDIS_EXPORTER_URL = "http://127.0.0.1:9188"

# psycopg v3 driver — matches database.py and migrations/env.py
DB_CONN_STR = (
    f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ---------------------------------------------------------------------------
# HTTP helpers — Makefile strips Proxyman PYTHONPATH and proxy env vars,
# so plain urllib.request works without interception.
# ---------------------------------------------------------------------------


def _fetch_json(url, timeout=5):
    """Fetch JSON from a localhost URL."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode()), resp.status
    except Exception as e:
        return {"error": str(e)}, 0


def _fetch_text(url, timeout=5):
    """Fetch raw text from a localhost URL."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode(), resp.status
    except Exception:
        return None, 0


def _check_reachable(url, timeout=3):
    """Return True if URL responds with any 2xx status."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Cached data fetchers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=15)
def fetch_health():
    return _fetch_json(f"{API_URL}/health")


@st.cache_data(ttl=30)
def fetch_metrics_text():
    return _fetch_text(f"{API_URL}/metrics")


@st.cache_data(ttl=30)
def query_prometheus(query):
    encoded = urllib.parse.quote(query, safe="")
    data, status = _fetch_json(f"{PROMETHEUS_URL}/api/v1/query?query={encoded}")
    if status == 200 and data.get("status") == "success":
        return data["data"]["result"]
    return []


# ---------------------------------------------------------------------------
# Sidebar — Connection info and diagnostics
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader("Connection Info")
    st.code(
        f"API:           {API_URL}\n"
        f"DB:            {DB_HOST}:{DB_PORT}/{DB_NAME}\n"
        f"DB user:       {DB_USER}\n"
        f"Redis:         127.0.0.1:{REDIS_PORT}\n"
        f"Prometheus:    {PROMETHEUS_URL}\n"
        f"PG Exporter:   {PG_EXPORTER_URL}\n"
        f"Redis Exporter:{REDIS_EXPORTER_URL}\n"
        f"Driver:        psycopg (v3)",
        language="text",
    )

    proxyman_in_path = "Proxyman" in os.environ.get("PYTHONPATH", "")
    if proxyman_in_path:
        st.error(
            "Proxyman detected in PYTHONPATH — use `make dashboard` to launch cleanly"
        )
    else:
        st.success("PYTHONPATH clean (no Proxyman)")

    st.divider()
    st.subheader("Service Reachability")
    checks = {
        f"API ({API_PORT})": f"{API_URL}/health",
        "Prometheus (9091)": f"{PROMETHEUS_URL}/-/ready",
        "PG Exporter (9187)": f"{PG_EXPORTER_URL}/metrics",
        "Redis Exporter (9188)": f"{REDIS_EXPORTER_URL}/metrics",
    }
    for name, url in checks.items():
        if _check_reachable(url):
            st.write(f"  {name}")
        else:
            st.write(f"  {name}")


# ---------------------------------------------------------------------------
# Main Dashboard
# ---------------------------------------------------------------------------

st.title("Ghost Backend Dashboard")
st.caption(f"Dev-only admin view — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ===== Section 1: Service Health =====
st.header("Service Health")

health_data, health_status = fetch_health()
col1, col2, col3 = st.columns(3)

with col1:
    if health_status == 200 and health_data.get("success"):
        st.success("API: Healthy")
        api_info = health_data.get("data", {})
        st.metric("Status", api_info.get("api", "unknown"))
    else:
        st.error(f"API: Unreachable ({health_status})")
        st.json(health_data)

with col2:
    if health_status == 200 and health_data.get("data", {}).get("database") == "healthy":
        st.success("PostgreSQL: Healthy (via API)")
    else:
        # Fallback: try direct connection
        try:
            conn = st.connection("ghost_db", type="sql", url=DB_CONN_STR)
            result = conn.query("SELECT 1 AS ok", ttl=30)
            if len(result) > 0:
                st.success("PostgreSQL: Up (direct)")
            else:
                st.warning("PostgreSQL: Unknown")
        except Exception as e:
            st.error(f"PostgreSQL: Down ({e})")

with col3:
    if health_status == 200 and health_data.get("data", {}).get("redis") == "healthy":
        st.success("Redis: Healthy (via API)")
    else:
        st.warning("Redis: Unknown — API health check didn't report Redis")


# ===== Section 2: Application Metrics (from /metrics) =====
st.header("Application Metrics")

metrics_text, metrics_status = fetch_metrics_text()

if metrics_text and metrics_status == 200:
    # Parse Prometheus text format into a dict of metric_name -> lines
    metric_lines = {}
    for line in metrics_text.split("\n"):
        if not line or line.startswith("#"):
            continue
        name = line.split("{")[0].split(" ")[0]
        metric_lines.setdefault(name, []).append(line)

    mcol1, mcol2, mcol3 = st.columns(3)

    # Active requests gauge
    with mcol1:
        active = metric_lines.get("ghost_http_requests_active", [])
        if active:
            val = active[0].split()[-1]
            st.metric("Active Requests", val)
        else:
            st.metric("Active Requests", "N/A")

    # Total requests counter
    with mcol2:
        total = metric_lines.get("ghost_http_requests_total", [])
        if total:
            total_sum = sum(float(l.split()[-1]) for l in total)
            st.metric("Total Requests", f"{total_sum:.0f}")
        else:
            st.metric("Total Requests", "N/A")

    # Unique endpoints hit
    with mcol3:
        st.metric("Metric Series", len(sum(metric_lines.values(), [])))

    # Request breakdown by endpoint
    total_lines = metric_lines.get("ghost_http_requests_total", [])
    if total_lines:
        st.subheader("Requests by Endpoint")
        rows = []
        for line in total_lines:
            try:
                labels_str = line.split("{")[1].split("}")[0]
                value = float(line.split()[-1])
                labels = {}
                for pair in labels_str.split(","):
                    k, _, v = pair.partition("=")
                    labels[k.strip()] = v.strip('"')
                rows.append(
                    {
                        "Method": labels.get("method", labels.get("endpoint", "?")),
                        "Endpoint": labels.get("endpoint", labels.get("path", "?")),
                        "Status": labels.get("status", "?"),
                        "Count": value,
                    }
                )
            except (IndexError, ValueError):
                continue
        if rows:
            st.dataframe(rows, width="stretch")

    with st.expander("Raw /metrics output"):
        st.code(metrics_text[:8000], language="text")
else:
    st.info(
        f"Metrics endpoint not available at {API_URL}/metrics "
        "(rate limited to 30/min — wait and retry)"
    )


# ===== Section 3: Database =====
st.header("Database")

try:
    conn = st.connection("ghost_db", type="sql", url=DB_CONN_STR)

    col_db1, col_db2 = st.columns(2)

    with col_db1:
        st.subheader("Tables")
        tables = conn.query(
            """
            SELECT tablename,
                   pg_size_pretty(pg_total_relation_size(quote_ident(tablename))) AS size
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
            """,
            ttl=60,
        )
        st.dataframe(tables, width="stretch")

    with col_db2:
        st.subheader("Connection Stats")
        db_stats = conn.query(
            """
            SELECT
                numbackends AS active_connections,
                xact_commit AS commits,
                xact_rollback AS rollbacks,
                blks_read AS blocks_read,
                blks_hit AS cache_hits,
                tup_returned AS rows_returned,
                tup_fetched AS rows_fetched,
                tup_inserted AS rows_inserted,
                tup_updated AS rows_updated,
                tup_deleted AS rows_deleted,
                pg_size_pretty(pg_database_size(current_database())) AS db_size
            FROM pg_stat_database
            WHERE datname = current_database()
            """,
            ttl=15,
        )
        if len(db_stats) > 0:
            row = db_stats.iloc[0]
            scol1, scol2, scol3 = st.columns(3)
            scol1.metric("Connections", row["active_connections"])
            scol2.metric("DB Size", row["db_size"])
            hits = row["cache_hits"]
            reads = row["blocks_read"]
            ratio = f"{hits / (hits + reads) * 100:.1f}%" if (hits + reads) > 0 else "N/A"
            scol3.metric("Cache Hit Ratio", ratio)

    # Active sessions
    st.subheader("Active Sessions")
    sessions = conn.query(
        """
        SELECT pid, state, wait_event_type, left(query, 100) AS query,
               now() - query_start AS duration
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND pid != pg_backend_pid()
          AND state IS NOT NULL
        ORDER BY query_start DESC NULLS LAST
        LIMIT 15
        """,
        ttl=10,
    )
    st.dataframe(sessions, width="stretch")

    # User/session counts (application tables)
    st.subheader("Application Data")
    try:
        app_stats = conn.query(
            """
            SELECT
                (SELECT count(*) FROM users) AS total_users,
                (SELECT count(*) FROM users WHERE is_active = true) AS active_users,
                (SELECT count(*) FROM user_sessions WHERE is_active = true) AS active_sessions,
                (SELECT count(*) FROM roles) AS roles,
                (SELECT count(*) FROM permissions) AS permissions
            """,
            ttl=30,
        )
        if len(app_stats) > 0:
            r = app_stats.iloc[0]
            acol1, acol2, acol3, acol4, acol5 = st.columns(5)
            acol1.metric("Total Users", r["total_users"])
            acol2.metric("Active Users", r["active_users"])
            acol3.metric("Active Sessions", r["active_sessions"])
            acol4.metric("Roles", r["roles"])
            acol5.metric("Permissions", r["permissions"])
    except Exception:
        st.caption("Application tables not yet created (run migrations)")

except Exception as e:
    st.warning(f"Cannot connect to database: {e}")
    st.info(
        f"Connection: `{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}` — "
        "Is Docker Compose running? `make up`"
    )


# ===== Section 4: Alembic Migrations =====
st.header("Alembic Migrations")

try:
    conn = st.connection("ghost_db", type="sql", url=DB_CONN_STR)
    alembic = conn.query(
        "SELECT version_num FROM alembic_version LIMIT 1",
        ttl=60,
    )
    if len(alembic) > 0:
        st.info(f"Current revision: `{alembic.iloc[0]['version_num']}`")
    else:
        st.warning("alembic_version table exists but is empty — run `alembic upgrade head`")
except Exception:
    st.warning(
        "alembic_version table not found — migrations have not been run yet. "
        "Run `alembic upgrade head` or set `SKIP_MIGRATIONS=false` in container env."
    )


# ===== Section 5: Prometheus PromQL =====
st.header("Prometheus Queries")

prom_reachable = _check_reachable(f"{PROMETHEUS_URL}/-/ready")

if prom_reachable:
    pcol1, pcol2 = st.columns(2)

    with pcol1:
        st.subheader("Request Rate (5m)")
        # Use the actual metric name from the ghost backend
        rate_data = query_prometheus(
            'rate(ghost_http_requests_total[5m])'
        )
        if rate_data:
            for r in rate_data:
                labels = r["metric"]
                value = float(r["value"][1])
                endpoint = labels.get("endpoint", labels.get("path", "?"))
                method = labels.get("method", "?")
                status = labels.get("status", "?")
                st.metric(
                    f"{method} {endpoint} [{status}]",
                    f"{value:.4f} req/s",
                )
        else:
            st.caption("No request rate data (no traffic in last 5 minutes)")

    with pcol2:
        st.subheader("Error Rate (5m)")
        err_data = query_prometheus(
            'rate(ghost_http_requests_total{status=~"5.."}[5m])'
        )
        if err_data:
            for r in err_data:
                value = float(r["value"][1])
                st.metric("5xx errors", f"{value:.4f} req/s")
        else:
            st.caption("No 5xx errors in last 5 minutes")

    # p95 latency
    st.subheader("Request Latency (p95)")
    p95_data = query_prometheus(
        'histogram_quantile(0.95, rate(ghost_http_request_duration_seconds_bucket[5m]))'
    )
    if p95_data:
        for r in p95_data:
            labels = r["metric"]
            value = float(r["value"][1])
            endpoint = labels.get("endpoint", labels.get("le", "?"))
            st.metric(f"p95 {endpoint}", f"{value * 1000:.1f} ms")
    else:
        st.caption("No latency data (no traffic in last 5 minutes)")

    # Exporter status
    st.subheader("Exporter Targets")
    targets_data = query_prometheus("up")
    if targets_data:
        rows = []
        for r in targets_data:
            labels = r["metric"]
            rows.append(
                {
                    "Job": labels.get("job", "?"),
                    "Instance": labels.get("instance", "?"),
                    "Up": "Yes" if r["value"][1] == "1" else "No",
                }
            )
        st.dataframe(rows, width="stretch")
else:
    st.warning(
        f"Prometheus not reachable at {PROMETHEUS_URL} — "
        "is the Level 2 monitoring stack running? (`make up-infra` in GGDC-System/)"
    )


# ===== Section 6: Redis (via API health) =====
st.header("Redis")

if health_status == 200:
    redis_status = health_data.get("data", {}).get("redis", "unknown")
    if redis_status == "healthy":
        st.success(f"Redis is healthy (127.0.0.1:{REDIS_PORT})")
    else:
        st.warning(f"Redis status: {redis_status}")
else:
    st.warning("Cannot determine Redis status — API unreachable")

# Redis exporter metrics
redis_exp_reachable = _check_reachable(f"{REDIS_EXPORTER_URL}/metrics")
if redis_exp_reachable:
    redis_text, _ = _fetch_text(f"{REDIS_EXPORTER_URL}/metrics")
    if redis_text:
        redis_metrics = {}
        for line in redis_text.split("\n"):
            if line.startswith("#") or not line:
                continue
            parts = line.split(" ")
            if len(parts) >= 2:
                redis_metrics[parts[0]] = parts[1]

        rcol1, rcol2, rcol3, rcol4 = st.columns(4)
        rcol1.metric(
            "Connected Clients",
            redis_metrics.get("redis_connected_clients", "N/A"),
        )
        mem = redis_metrics.get("redis_memory_used_bytes", "0")
        try:
            mem_mb = f"{int(float(mem)) / 1024 / 1024:.1f} MB"
        except ValueError:
            mem_mb = "N/A"
        rcol2.metric("Memory Used", mem_mb)
        rcol3.metric(
            "Total Commands",
            redis_metrics.get("redis_commands_processed_total", "N/A"),
        )
        rcol4.metric(
            "Uptime (s)",
            redis_metrics.get("redis_uptime_in_seconds", "N/A"),
        )
else:
    st.caption(
        f"Redis exporter not reachable at {REDIS_EXPORTER_URL} — "
        "metrics unavailable"
    )


# --- Footer ---
st.divider()
st.caption(
    "Dev-only dashboard — do not expose to production. "
    "Source: `tools/streamlit_dashboard.py` | Launch: `make dashboard`"
)
