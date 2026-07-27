#!/usr/bin/env bash
# Initialize file-backed Docker secrets for Ghost Backend.
#
# Writes .secrets/<name> (gitignored, mode 0600) for each secret consumed by
# docker-compose.yml. Mirrors the-system/scripts/init-docker-secrets.sh.
#
# Usage:
#   ./scripts/init-docker-secrets.sh              # prompt for any missing secret
#   ./scripts/init-docker-secrets.sh --generate   # generate random values for missing secrets
#   ./scripts/init-docker-secrets.sh --force      # overwrite existing values too
#
# Canonical source of record is 1Password "GGDC / ghost-backend". Generated
# values are for local development; paste the real ones for anything shared.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SECRETS_DIR="$PROJECT_ROOT/.secrets"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Must match the `secrets:` block in docker-compose.yml.
SECRETS=(jwt_secret api_key)

GENERATE=false
FORCE=false
for arg in "$@"; do
  case "$arg" in
    --generate) GENERATE=true ;;
    --force)    FORCE=true ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

for name in "${SECRETS[@]}"; do
  file="$SECRETS_DIR/$name"

  if [ -s "$file" ] && [ "$FORCE" = false ]; then
    log_info "$name already set — skipping (use --force to overwrite)"
    continue
  fi

  if [ "$GENERATE" = true ]; then
    # No trailing newline: read_secret uses $(cat), and a stray newline in a
    # password is the kind of thing that fails only at authentication time.
    printf '%s' "$(openssl rand -base64 36 | tr -d '\n/+=' | cut -c1-48)" > "$file"
    log_info "generated $name"
  else
    read -r -s -p "Enter value for $name (empty to skip): " value
    echo
    if [ -z "$value" ]; then
      log_warn "$name skipped — container will fall back to compose defaults"
      continue
    fi
    printf '%s' "$value" > "$file"
    log_info "wrote $name"
  fi

  chmod 600 "$file"
done

log_info "Secrets in $SECRETS_DIR"
log_warn "Never commit .secrets/ — it is gitignored. Rotate via 1Password 'GGDC / ghost-backend'."
