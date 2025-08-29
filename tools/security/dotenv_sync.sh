#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

if [ "${ALLOW_DOTENV_SECRETS:-}" != "true" ]; then
  echo "Refusing to write secrets to disk. Set ALLOW_DOTENV_SECRETS=true to proceed."
  exit 1
fi

# Ensure .env is ignored
if ! grep -qE '(^|/)\.env($|/)' .gitignore 2>/dev/null; then
  echo "Error: .env is not ignored by .gitignore. Add '.env' to .gitignore first."
  exit 1
fi

. ./scripts/secrets/keychain.sh

DB_USER="${DB_USER:-ghost}"
DB_NAME="${DB_NAME:-ghost_db}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_PASSWORD="$(kc_get "Ghost DB Password" "$DB_USER")"

if [ -z "$DB_PASSWORD" ]; then
  echo "Error: No DB password in Keychain for account '$DB_USER'. Run 'make env/keychain-setup' first."
  exit 1
fi

umask 177 # files as 600
cat > .env <<ENV
# Generated for local development. Do not commit.
DB_USER=$DB_USER
DB_NAME=$DB_NAME
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_PASSWORD=$DB_PASSWORD
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=disable
ENV

chmod 600 .env
echo ".env written with mode 600."

