SHELL := /bin/bash

PROJECT_NAME := Ghost
DB_NAME := ghost_db
DB_USER := ghost
DB_HOST := localhost
DB_PORT := 5432

KC_SERVICE_DB := Ghost DB Password
KC_SERVICE_PG_SUPER := Ghost Postgres Superuser Password

PORT := /opt/local/bin/port
PSQL := /opt/local/bin/psql
PG_ISREADY := /opt/local/bin/pg_isready
PG_BINDIR16 := /opt/local/lib/postgresql16/bin
PGDATA16 := /opt/local/var/db/postgresql16/defaultdb

.PHONY: db/install db/init db/start db/stop db/status db/create db/migrate-old \
       env/keychain-setup env/envrc env/dotenv-sync tools/verify-path \
       up down logs ps build test test-integration lint format check migrate health dashboard \
       mk/start mk/stop mk/status mk/dashboard mk/deploy mk/delete mk/logs mk/shell mk/health mk/gcp-mount \
       sk/dev sk/run sk/build sk/delete

tools/verify-path:
	@. ./scripts/macports/env_helpers.sh; command -v psql >/dev/null && psql --version || true

db/install:
	@if [ ! -x "$(PORT)" ]; then ./scripts/macports/install_macports.sh; fi
	@sudo "$(PORT)" -v selfupdate
	@sudo "$(PORT)" install postgresql16 postgresql16-server
	@sudo "$(PORT)" select --set postgresql postgresql16

db/init:
	@mkdir -p "$(PGDATA16)"
	@if [ ! -f "$(PGDATA16)/PG_VERSION" ]; then \
	  if ! security find-generic-password -s "$(KC_SERVICE_PG_SUPER)" -a postgres >/dev/null 2>&1; then \
	    echo "No Keychain superuser password; run 'make env/keychain-setup' first."; exit 1; \
	  fi; \
	  tmp_pw="$$(mktemp)"; \
	  security find-generic-password -s "$(KC_SERVICE_PG_SUPER)" -a postgres -w > "$$tmp_pw"; \
	  sudo -u postgres "$(PG_BINDIR16)/initdb" -D "$(PGDATA16)" -A scram-sha-256 -U postgres --pwfile="$$tmp_pw"; \
	  rm -f "$$tmp_pw"; \
	else \
	  echo "PostgreSQL 16 data directory already initialized."; \
	fi

db/start:
	@sudo "$(PORT)" load postgresql16-server || true
	@sleep 1
	@$(MAKE) db/status

db/stop:
	@sudo "$(PORT)" unload postgresql16-server || true

db/status:
	@echo "Service status:"
	@launchctl list | grep -i macports.*postgresql16 || true
	@echo "pg_isready:"
	@$(PG_ISREADY) -h "$(DB_HOST)" -p "$(DB_PORT)" || true
	@$(PSQL) --version

db/create:
	@if ! security find-generic-password -s "$(KC_SERVICE_DB)" -a "$(DB_USER)" >/dev/null 2>&1; then \
	  echo "No DB user password in Keychain; run 'make env/keychain-setup' first."; exit 1; \
	fi
	@export PGPASSWORD="$$(security find-generic-password -s "$(KC_SERVICE_PG_SUPER)" -a postgres -w)"; \
	 DBPW="$$(security find-generic-password -s "$(KC_SERVICE_DB)" -a "$(DB_USER)" -w)"; \
	 $(PSQL) -h "$(DB_HOST)" -U postgres -v ON_ERROR_STOP=1 -c "DO $$BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='$(DB_USER)') THEN CREATE ROLE $(DB_USER) WITH LOGIN PASSWORD '$$DBPW'; END IF; END$$;"; \
	 $(PSQL) -h "$(DB_HOST)" -U postgres -v ON_ERROR_STOP=1 -c "DO $$BEGIN IF NOT EXISTS (SELECT FROM pg_database WHERE datname='$(DB_NAME)') THEN CREATE DATABASE $(DB_NAME) OWNER $(DB_USER); END IF; END$$;"; \
	 $(PSQL) -h "$(DB_HOST)" -U postgres -d "$(DB_NAME)" -v ON_ERROR_STOP=1 -c "GRANT ALL ON SCHEMA public TO $(DB_USER);"; \
	 $(PSQL) -h "$(DB_HOST)" -U postgres -d "$(DB_NAME)" -v ON_ERROR_STOP=1 -c "GRANT CREATE ON SCHEMA public TO $(DB_USER);"

db/migrate-old:
	@./scripts/macports/migrate_old.sh

env/keychain-setup:
	@./scripts/secrets/keychain.sh kc_require_or_set "$(KC_SERVICE_DB)" "$(DB_USER)"
	@./scripts/secrets/keychain.sh kc_require_or_set "$(KC_SERVICE_PG_SUPER)" "postgres"

env/envrc:
	@echo 'source_env_if_exists() { [ -f "$$1" ] && . "$$1"; }' > .envrc
	@echo 'source_env_if_exists ./scripts/macports/env_helpers.sh' >> .envrc
	@echo 'source_env_if_exists ./scripts/secrets/runtime_env.sh' >> .envrc
	@echo ".envrc written. If using direnv: direnv allow"

env/dotenv-sync:
	@ALLOW_DOTENV_SECRETS=true ./scripts/secrets/dotenv_sync.sh

# ──────────────────────────────────────────────
# Docker targets
# ──────────────────────────────────────────────

up:
	@docker compose up -d
	@echo "Ghost Backend started — http://localhost:8801/health"

down:
	@docker compose down

logs:
	@docker compose logs -f backend

ps:
	@docker compose ps

build:
	@docker compose build

# ──────────────────────────────────────────────
# Development targets
# ──────────────────────────────────────────────

test:
	@python -m pytest tests/ --cov=src/ghost --cov-report=term -q

test-integration:
	@echo "Starting Docker services for integration tests..."
	@docker compose up -d postgres redis
	@echo "Waiting for services..."
	@sleep 5
	@DB_HOST=localhost DB_PORT=5433 DB_NAME=ghost DB_USER=postgres DB_PASSWORD=ghost_password \
	 REDIS_HOST=localhost REDIS_PORT=6380 \
	 python -m pytest tests/ -m "integration" --cov=src/ghost --cov-report=term -q; \
	 EXIT_CODE=$$?; \
	 echo "Stopping Docker services..."; \
	 docker compose stop postgres redis; \
	 exit $$EXIT_CODE

lint:
	@python -m flake8 src/ --max-line-length=120 --count --statistics
	@python -m mypy src/ghost/ --ignore-missing-imports

format:
	@python -m black src/ tests/
	@python -m isort src/ tests/

check: lint test
	@echo "All checks passed."

migrate:
	@alembic upgrade head

health:
	@curl -sf http://localhost:8801/health | python -m json.tool || echo "Backend not reachable"

dashboard:
	@docker compose --profile dashboard up -d streamlit-dashboard
	@echo "Streamlit dashboard started — http://localhost:8502"

openapi:
	@python tools/scripts/export_openapi.py docs/openapi.json
	@echo "OpenAPI schema exported to docs/openapi.json"

# ──────────────────────────────────────────────
# Minikube targets
# ──────────────────────────────────────────────

MK_NAMESPACE := ghost-backend

mk/start:
	@minikube start --cpus=4 --memory=8192 --driver=docker
	@echo "Minikube started. Run 'make sk/dev' or 'make mk/deploy' next."

mk/stop:
	@minikube stop

mk/status:
	@minikube status || true
	@echo "---"
	@kubectl get pods -n $(MK_NAMESPACE) 2>/dev/null || echo "Namespace $(MK_NAMESPACE) not found — deploy first."

mk/dashboard:
	@minikube dashboard &

mk/deploy:
	@eval $$(minikube docker-env) && docker build -t ghost-backend:latest .
	@kubectl apply -k k8s/overlays/minikube/
	@echo "Deployed. Waiting for pods..."
	@kubectl rollout status deployment/backend -n $(MK_NAMESPACE) --timeout=120s || true
	@kubectl get pods -n $(MK_NAMESPACE)

mk/delete:
	@kubectl delete -k k8s/overlays/minikube/ --ignore-not-found
	@echo "Resources deleted."

mk/logs:
	@kubectl logs -f -l app=backend -n $(MK_NAMESPACE)

mk/shell:
	@kubectl exec -it $$(kubectl get pod -l app=backend -n $(MK_NAMESPACE) -o jsonpath='{.items[0].metadata.name}') -n $(MK_NAMESPACE) -- /bin/bash

mk/health:
	@curl -sf http://localhost:8801/health | python -m json.tool || echo "Backend not reachable (is port-forward running?)"

mk/gcp-mount:
	@echo "Mounting ~/.config/gcloud into minikube at /host-adc ..."
	@minikube mount ~/.config/gcloud:/host-adc &
	@echo "GCP ADC mount started in background. Use 'fg' or kill the process to stop."

# ──────────────────────────────────────────────
# Skaffold targets
# ──────────────────────────────────────────────

sk/dev:
	@skaffold dev --port-forward

sk/run:
	@skaffold run --port-forward

sk/build:
	@skaffold build

sk/delete:
	@skaffold delete

