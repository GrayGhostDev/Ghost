# Kubernetes — Ghost Backend

## Kustomize Overlay Structure

```
k8s/
├── base/                      # Shared manifests
│   ├── kustomization.yaml
│   ├── backend-deployment.yaml
│   ├── backend-configmap.yaml
│   ├── backend-service.yaml
│   ├── postgres-statefulset.yaml
│   ├── postgres-service.yaml
│   ├── redis-deployment.yaml
│   └── redis-service.yaml
├── overlays/
│   ├── minikube/              # Local development
│   │   ├── kustomization.yaml
│   │   ├── patches/
│   │   └── secretGenerator (literals from .env)
│   └── production/            # Production (placeholder)
│       └── kustomization.yaml
```

## ConfigMap → .env Mapping

| ConfigMap Key | .env Equivalent | Notes |
|---|---|---|
| `ENVIRONMENT` | `ENVIRONMENT` | `development` in minikube |
| `API_HOST` | `API_HOST` | `0.0.0.0` in K8s (pod-internal) |
| `API_PORT` | `API_PORT` | `8801` |
| `DB_HOST` | `DB_HOST` | `postgres` (K8s service name) |
| `DB_PORT` | `DB_PORT` | `5432` (internal) |
| `REDIS_HOST` | `REDIS_HOST` | `redis` (K8s service name) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://host.minikube.internal:4317` |

## Secret Management

| Environment | Method |
|---|---|
| Minikube | `secretGenerator` with literal values from `.env` |
| GKE (future) | External Secrets Operator → GCP Secret Manager |
| Cloud Run (future) | GCP Secret Manager native references |

## Skaffold Dev Loop

```bash
make sk/dev     # Start dev loop with port-forward + live reload
make sk/run     # One-shot deploy
make sk/delete  # Tear down
```

Skaffold watches `src/` for changes and rebuilds/redeploys automatically.

## Port Forwarding

Same host ports as Docker Compose for consistency:
- API: `localhost:8801` → backend:8801
- PostgreSQL: `localhost:5433` → postgres:5432
- Redis: `localhost:6380` → redis:6379

## GCP Auth Mount (Minikube)

```bash
make mk/gcp-mount   # Mount GCP ADC into minikube (background process)
```

Mounts `~/.config/gcloud/application_default_credentials.json` into the minikube VM.
Required for GCP Secret Manager overlay (`GCP_SECRET_PROJECT=sylvan-flight-476922-m7`).

## Common Operations

```bash
make mk/start    # Start minikube (4 CPU, 8GB RAM, docker driver)
make mk/status   # minikube status + pod listing
make mk/logs     # Tail backend pod logs
make mk/shell    # Exec into backend pod
make mk/health   # curl localhost:8801/health
make mk/deploy   # Direct kubectl apply
make mk/delete   # Tear down K8s resources
make mk/stop     # Stop minikube VM
```
