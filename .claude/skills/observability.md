# Observability — Ghost Backend

## OpenTelemetry Configuration

Ghost Backend uses OTEL with **gRPC protocol on port 4317** (not HTTP 4318).

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317   # Docker Compose
OTEL_EXPORTER_OTLP_ENDPOINT=http://host.minikube.internal:4317  # Minikube
OTEL_SERVICE_NAME=ghost-backend
OTEL_RESOURCE_ATTRIBUTES=service.namespace=ggdc,deployment.environment=development
```

The Python SDK (`opentelemetry-exporter-otlp-proto-grpc`) uses gRPC by default.
Never use port 4318 (HTTP) unless the exporter is explicitly configured for HTTP.

## Prometheus Exporters

| Exporter | Host Port | Container Port | Target |
|---|---|---|---|
| postgres-exporter | 9187 | 9187 | PostgreSQL metrics |
| redis-exporter | 9188 | 9121 | Redis metrics |

Both exporters join `ggdc-shared-net` for Level 2 Prometheus scraping.

## GGDC Docker Label Conventions

All Ghost Backend services must include these labels:

```yaml
labels:
  com.ggdc.project: "GGDC-System"
  com.ggdc.service: "<container-name>"
  com.ggdc.level: "2"
```

Services exposing metrics add:
```yaml
  com.ggdc.scrape: "true"
  com.ggdc.metrics_port: "<port>"
```

Data services (postgres, redis) do NOT get `com.ggdc.scrape` — their exporters handle metrics.

## Jaeger Trace Queries

Jaeger UI: `http://localhost:16686`

Common queries:
- All ghost-backend traces: Service = `ghost-backend`
- Slow requests: Service = `ghost-backend`, Min Duration = `500ms`
- Error traces: Service = `ghost-backend`, Tags = `error=true`

## PromQL Patterns

```promql
# Ghost Backend API request rate
rate(http_requests_total{service="ghost-backend"}[5m])

# PostgreSQL connection pool usage
pg_stat_activity_count{datname="ghost"}

# Redis memory usage
redis_memory_used_bytes{instance=~".*:9121"}

# Redis exporter up
up{job=~".*redis-exporter.*"}
```

## Structured Logging

Ghost Backend uses Loguru for structured logging. Logs are collected by Grafana Alloy
and sent to Loki (Level 2).

LogQL query patterns:
```logql
{container="ghost-be-api"} |= "ERROR"
{com_ggdc_project="GGDC-System"} | json | level="ERROR"
```
