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

.PHONY: db/install db/init db/start db/stop db/status db/create db/migrate-old env/keychain-setup env/envrc env/dotenv-sync tools/verify-path

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

