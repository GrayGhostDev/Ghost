#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"

find_old_brew_pg() {
  command -v brew >/dev/null 2>&1 || return 1
  local ver prefix
  # Prefer versioned formulae
  ver="$(brew list --versions | awk '/postgresql@[0-9]+/ {print $1}' | sed 's/postgresql@//' | sort -nr | head -1)"
  if [ -n "${ver:-}" ]; then
    prefix="$(brew --prefix "postgresql@${ver}")" || return 1
    echo "$prefix/bin/pg_dumpall"
    return 0
  fi
  # Fallback unversioned
  if brew list --versions | grep -q '^postgresql '; then
    prefix="$(brew --prefix postgresql)" || return 1
    echo "$prefix/bin/pg_dumpall"
    return 0
  fi
  return 1
}

find_old_macports_pg() {
  if ! command -v port >/dev/null 2>&1; then return 1; fi
  # Look for highest installed postgresql1X (excluding 16)
  local ver bin
  ver="$(port installed | awk '/postgresql1[0-9] @/ {print $1}' | sed 's/postgresql//' | sort -nr | grep -v '^16$' | head -1 || true)"
  if [ -n "${ver:-}" ]; then
    bin="/opt/local/lib/postgresql${ver}/bin/pg_dumpall"
    [ -x "$bin" ] && { echo "$bin"; return 0; }
  fi
  return 1
}

stop_old_services() {
  if command -v brew >/dev/null 2>&1; then
    brew services list 2>/dev/null | awk 'NR>1 && /postgres/ {print $1}' | while read -r svc; do
      echo "Stopping Homebrew service $svc ..."
      brew services stop "$svc" || true
    done
  fi
  if command -v port >/dev/null 2>&1; then
    port installed | awk '/postgresql1[0-9]-server/ {print $1}' | grep -v 'postgresql16-server' | while read -r p; do
      echo "Unloading MacPorts service $p ..."
      sudo port unload "$p" || true
    done
  fi
}

restore_into_v16() {
  local dumpfile="$1"
  if [ ! -s "$dumpfile" ]; then
    echo "Dump file missing or empty: $dumpfile"; exit 1
  fi
  echo "Restoring into PostgreSQL 16 ..."
  # Use postgres superuser; allow statements to continue on harmless 'already exists' errors
  export PGPASSWORD="$(security find-generic-password -s "Ghost Postgres Superuser Password" -a postgres -w 2>/dev/null || true)"
  psql -h localhost -U postgres -f "$dumpfile" || {
    echo "Restore finished with non-fatal errors (likely duplicates). Review output above."
  }
}

main() {
  local old_dumpall=""
  old_dumpall="$(find_old_brew_pg || true)"
  if [ -z "$old_dumpall" ]; then
    old_dumpall="$(find_old_macports_pg || true)"
  fi
  if [ -z "$old_dumpall" ]; then
    echo "No older PostgreSQL installation detected. Nothing to migrate."
    exit 0
  fi

  echo "Detected old pg_dumpall at: $old_dumpall"
  read -r -p "Proceed to stop old services and dump/restore all databases into v16? [y/N] " ans
  case "$ans" in
    y|Y) : ;;
    *) echo "Aborted."; exit 1 ;;
  esac

  stop_old_services

  # Ensure v16 is running
  sudo port load postgresql16-server || true
  sleep 2

  ts="$(date +%Y%m%d_%H%M%S)"
  dump="${BACKUP_DIR}/postgres_all_${ts}.sql"
  echo "Dumping all databases and globals to ${dump} ..."
  "$old_dumpall" > "$dump"

  echo "Restoring dump into v16 ..."
  restore_into_v16 "$dump"

  echo "Migration attempt completed. Verify roles and databases."
}

main "$@"

