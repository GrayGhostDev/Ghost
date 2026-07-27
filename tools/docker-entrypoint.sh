#!/bin/sh
# Docker entrypoint for Ghost Backend — Docker secrets → environment.
#
# Runs before tools/docker_entrypoint.py and exists only to materialize
# file-backed secrets. Values in `environment:` used to carry JWT_SECRET and
# API_KEY in the clear, where `docker inspect` and the compose config output
# both exposed them.
#
# Mirrors the-system/services/*/docker-entrypoint.sh so the two stacks share one
# pattern. Missing secrets warn rather than fail: development runs without a
# .secrets/ directory and falls back to compose `environment:` defaults. It is
# tools/docker_entrypoint.py that refuses to boot without them outside dev.

set -e

# A secret file wins over an inherited environment variable — a file-backed
# secret is the more deliberate source, and silently preferring a stale env var
# is how a rotated credential fails to take effect.
read_secret() {
  secret_name=$1
  env_var=$2
  secret_file="/run/secrets/${secret_name}"

  if [ -f "$secret_file" ]; then
    export "$env_var"="$(cat "$secret_file")"
    echo "✓ Loaded secret: ${secret_name} → ${env_var}"
  fi
}

if [ -d /run/secrets ]; then
  echo "🔐 Loading Docker secrets..."
  # Only these two. DB_PASSWORD/REDIS_PASSWORD stay env-sourced so the client
  # and the server (postgres/redis) cannot drift apart — see docker-compose.yml.
  read_secret "jwt_secret" "JWT_SECRET"
  read_secret "api_key"    "API_KEY"
else
  echo "ℹ️  No /run/secrets mount — using environment variables as provided."
fi

exec "$@"
