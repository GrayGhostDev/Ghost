#!/usr/bin/env bash
set -euo pipefail

# Load helper
. "$(dirname "${BASH_SOURCE[0]}")/keychain.sh"

# Defaults for local dev
export DB_USER="${DB_USER:-ghost}"
export DB_NAME="${DB_NAME:-ghost_db}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"

# Attempt to read from Keychain; allow override via env (e.g., CI)
if [ -z "${DB_PASSWORD:-}" ]; then
  DB_PASSWORD="$(kc_get "Ghost DB Password" "$DB_USER" || true)"
  if [ -z "$DB_PASSWORD" ]; then
    echo "Warning: DB_PASSWORD not in Keychain for account '$DB_USER'."
    echo "Set it with: scripts/secrets/keychain.sh via Make target env/keychain-setup"
  fi
  export DB_PASSWORD
fi

# Provide to libpq clients
export PGPASSWORD="$DB_PASSWORD"

# Compose DATABASE_URL for frameworks that use it
if [ -n "${DB_PASSWORD:-}" ]; then
  export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=disable"
fi

