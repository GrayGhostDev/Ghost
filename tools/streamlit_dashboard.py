"""
Ghost Backend — Dev Admin Dashboard (Streamlit)

Dev-only dashboard for monitoring Ghost Backend services.
NOT for production — runs on the host via `make dashboard`.

Usage:
  make dashboard
  # or directly:
  streamlit run tools/streamlit_dashboard.py --server.port=8502 --server.address=127.0.0.1
"""

import os
import urllib.request
import json
import ssl
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

API_URL = f"http://127.0.0.1:{API_PORT}"
PROMETHEUS_URL = "http://127.0.0.1:9091"

# psycopg v3 driver — matches database.py and migrations/env.py
DB_CONN_STR = (
    f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


# ---------------------------------------------------------------------------
# HTTP helper — bypass Proxyman for localhost calls
# ---------------------------------------------------------------------------

def _fetch_json(url, timeout=5):
    """Fetch JSON from a localhost URL, bypassing any HTTP proxy."""
    try:
        # ProxyHandler({}) = no proxies, bypasses Proxyman injection
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(url)
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return json.loads(body), resp.status
    except Exception as e:
        return {"error": str(e)}, 0


def _fetch_text(url, timeout=5):
    """Fetch raw text from a localhost URL, bypassing any HTTP proxy."""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(url)
        with opener.open(req, timeout=timeout) as resp:
            return resp.read().decode(), resp.status
    except Exception:
        return None, 0


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

st.title("👻 Ghost Backend Dashboard")
st.caption(f"Dev-only admin view — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --- Health Status ---
st.header("Service Health")

col1, col2, col3 = st.columns(3)


@st.cache_data(ttl=30)
def fetch_health():
    return _fetch_json(f"{API_URL}/health")


@st.cache_data(ttl=30)
def fetch_metrics_text():
    return _fetch_text(f"{API_URL}/metrics")


@st.cache_data(ttl=30)
def query_prometheus(query):
    data, status = _fetch_json(
        f"{PROMETHEUS_URL}/api/v1/query?query={urllib.request.quote(query)}"
    )
    if status == 200 and data.get("status") == "success":
        return data["data"]["result"]
    return []


health_data, health_status = fetch_health()

with col1:
    if health_status == 200:
        st.success("API: Healthy")
    else:
        st.error(f"API: Unreachable ({health_status})")
    st.json(health_data)

with col2:
    # Check PostgreSQL via pg exporter
    pg_up = query_prometheus('pg_up{job=~".*ghost.*"}')
    if pg_up and len(pg_up) > 0 and pg_up[0]["value"][1] == "1":
        st.success("PostgreSQL: Up")
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
    redis_up = query_prometheus('redis_up{job=~".*ghost.*"}')
    if redis_up and len(redis_up) > 0 and redis_up[0]["value"][1] == "1":
        st.success("Redis: Up")
    else:
        # Fallback: check via API health (already fetched)
        if health_status == 200 and health_data.get("data", {}).get("redis") == "healthy":
            st.success("Redis: Up (via API)")
        else:
            st.warning("Redis: Status unknown (exporter not reachable)")

# --- Database Info ---
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
        st.subheader("Active Sessions")
        sessions = conn.query(
            """
            SELECT pid, state, query_start, left(query, 80) AS query
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND pid != pg_backend_pid()
            ORDER BY query_start DESC NULLS LAST
            LIMIT 10
            """,
            ttl=15,
        )
        st.dataframe(sessions, width="stretch")

except Exception as e:
    st.warning(f"Cannot connect to database: {e}")
    st.info(
        f"Connection: `{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}` — "
        "Is Docker Compose running? `make up`"
    )

# --- Alembic Migration Status ---
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
        st.warning("No alembic_version table found — migrations may not have run")
except Exception:
    st.info("Alembic version table not available")

# --- Prometheus Metrics ---
st.header("Prometheus Metrics")

metrics_text, metrics_status = fetch_metrics_text()

if metrics_text and metrics_status == 200:
    lines = [
        line
        for line in metrics_text.split("\n")
        if line and not line.startswith("#")
    ]
    st.metric("Total metric series", len(lines))

    with st.expander("Raw /metrics output"):
        st.code(metrics_text[:5000], language="text")
else:
    st.info("Metrics endpoint not available at /metrics")

# --- PromQL Queries ---
prom_col1, prom_col2 = st.columns(2)

with prom_col1:
    st.subheader("Request Rate (5m)")
    rate_data = query_prometheus(
        'rate(http_requests_total{service="ghost-backend"}[5m])'
    )
    if rate_data:
        for r in rate_data:
            labels = r["metric"]
            value = float(r["value"][1])
            st.metric(
                f"{labels.get('method', '?')} {labels.get('path', '?')}",
                f"{value:.2f} req/s",
            )
    else:
        st.caption("No request rate data")

with prom_col2:
    st.subheader("Error Rate (5m)")
    err_data = query_prometheus(
        'rate(http_requests_total{service="ghost-backend",status=~"5.."}[5m])'
    )
    if err_data:
        for r in err_data:
            value = float(r["value"][1])
            st.metric("5xx errors", f"{value:.4f} req/s")
    else:
        st.caption("No error rate data")

# --- Configuration (sidebar) ---
with st.sidebar:
    st.subheader("Connection Info")
    st.code(
        f"API:        {API_URL}\n"
        f"DB:         {DB_HOST}:{DB_PORT}/{DB_NAME}\n"
        f"Prometheus: {PROMETHEUS_URL}\n"
        f"Driver:     psycopg (v3)",
        language="text",
    )
    if os.environ.get("PROXYMAN_ENABLED") == "true":
        st.warning("Proxyman active — HTTP calls bypass proxy via ProxyHandler({})")

# --- Footer ---
st.divider()
st.caption(
    "Dev-only dashboard — do not expose to production. "
    "Source: `tools/streamlit_dashboard.py`"
)
