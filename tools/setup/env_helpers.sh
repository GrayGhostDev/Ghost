#!/usr/bin/env bash
# Source this in project-local shells to prefer MacPorts.
# POSIX-friendly enough for bash/zsh.

_macports_path="/opt/local/bin:/opt/local/sbin"

# Prepend MacPorts paths if not already at front
case ":$PATH:" in
  *":/opt/local/bin:"*) : ;;
  *) export PATH="${_macports_path%%:*}:$PATH" ;;
esac
case ":$PATH:" in
  *":/opt/local/sbin:"*) : ;;
  *) export PATH="/opt/local/sbin:$PATH" ;;
esac

# Function to run curl without Proxyman SSL interference
safe_curl() {
  local old_ca_bundle="${CURL_CA_BUNDLE:-}"
  local old_ssl_dir="${SSL_CERT_DIR:-}"
  local old_ssl_file="${SSL_CERT_FILE:-}"
  local old_ssl_path="${SSL_CERT_PATH:-}"
  local old_https_bundle="${HTTPS_CA_BUNDLE:-}"
  local old_requests_bundle="${REQUESTS_CA_BUNDLE:-}"
  
  # Clear all SSL-related env vars that might interfere
  unset CURL_CA_BUNDLE SSL_CERT_DIR SSL_CERT_FILE SSL_CERT_PATH HTTPS_CA_BUNDLE REQUESTS_CA_BUNDLE
  
  # Run curl with arguments
  curl "$@"
  local exit_code=$?
  
  # Restore SSL environment
  [ -n "$old_ca_bundle" ] && export CURL_CA_BUNDLE="$old_ca_bundle"
  [ -n "$old_ssl_dir" ] && export SSL_CERT_DIR="$old_ssl_dir"
  [ -n "$old_ssl_file" ] && export SSL_CERT_FILE="$old_ssl_file"
  [ -n "$old_ssl_path" ] && export SSL_CERT_PATH="$old_ssl_path"
  [ -n "$old_https_bundle" ] && export HTTPS_CA_BUNDLE="$old_https_bundle"
  [ -n "$old_requests_bundle" ] && export REQUESTS_CA_BUNDLE="$old_requests_bundle"
  
  return $exit_code
}

# Verify psql resolution (no output if correct)
if command -v psql >/dev/null 2>&1; then
  _psql_path="$(command -v psql)"
  if [ "$_psql_path" != "/opt/local/bin/psql" ]; then
    echo "Warning: psql resolves to $_psql_path (not /opt/local/bin/psql)."
    echo "Consider running: sudo port select --set postgresql postgresql16"
  fi
fi

unset _macports_path _psql_path

