"""
Ghost Backend — Dev Admin Dashboard (Streamlit)

Dev-only dashboard for monitoring Ghost Backend services.
NOT for production — runs behind a compose profile ("dashboard").

Usage:
  streamlit run tools/streamlit_dashboard.py
  # or via compose:
  docker compose --profile dashboard up -d streamlit-dashboard
"""

import streamlit as st
import requests
import json
from datetime import datetime

st.set_page_config(
    page_title="Ghost Backend Dashboard",
    page_icon="👻",
    layout="wide",
)

# --- Configuration ---
API_URL = "http://localhost:8801"
PROMETHEUS_URL = "http://localhost:9091"
DB_CONN_STR = "postgresql://postgres:ghost_password@localhost:5433/ghost"

st.title("👻 Ghost Backend Dashboard")
st.caption(f"Dev-only admin view — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --- Health Status ---
st.header("Service Health")

col1, col2, col3 = st.columns(3)


@st.cache_data(ttl=30)
def fetch_health():
    """Fetch API health status."""
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        return resp.json(), resp.status_code
    except Exception as e:
        return {"error": str(e)}, 0


@st.cache_data(ttl=30)
def fetch_metrics_text():
    """Fetch Prometheus metrics endpoint."""
    try:
        resp = requests.get(f"{API_URL}/metrics", timeout=5)
        return resp.text, resp.status_code
    except Exception:
        return None, 0


@st.cache_data(ttl=30)
def query_prometheus(query):
    """Run a PromQL query against Level 2 Prometheus."""
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5,
        )
        data = resp.json()
        if data.get("status") == "success":
            return data["data"]["result"]
        return []
    except Exception:
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
            conn = st.connection(
                "ghost_db",
                type="sql",
                url=DB_CONN_STR,
            )
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
            SELECT tablename, pg_size_pretty(pg_total_relation_size(quote_ident(tablename)))
                   AS size
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
            """,
            ttl=60,
        )
        st.dataframe(tables, use_container_width=True)

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
        st.dataframe(sessions, use_container_width=True)

except Exception as e:
    st.warning(f"Cannot connect to database: {e}")
    st.info("Is Docker Compose running? `make up`")

# --- Alembic Migration Status ---
st.header("Alembic Migrations")

try:
    conn = st.connection("ghost_db", type="sql", url=DB_CONN_STR)
    alembic = conn.query(
        """
        SELECT version_num
        FROM alembic_version
        LIMIT 1
        """,
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
    # Parse key metrics
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

# --- Footer ---
st.divider()
st.caption(
    "Dev-only dashboard — do not expose to production. "
    "Source: `tools/streamlit_dashboard.py`"
)
