#!/bin/bash
# ============================================================================
# GHOST BACKEND - PROXYMAN-SAFE MAKE WRAPPER
# ============================================================================
# This script temporarily disables Proxyman SSL certificates for make commands
# that need to download files via curl, then restores them afterward.

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Proxyman SSL variables are set
is_proxyman_active() {
    [[ -n "${CURL_CA_BUNDLE:-}" ]] && [[ "$CURL_CA_BUNDLE" == *"proxyman"* ]]
}

# Save current SSL environment
save_ssl_env() {
    export SAVED_CURL_CA_BUNDLE="${CURL_CA_BUNDLE:-}"
    export SAVED_SSL_CERT_DIR="${SSL_CERT_DIR:-}"
    export SAVED_SSL_CERT_FILE="${SSL_CERT_FILE:-}"
    export SAVED_SSL_CERT_PATH="${SSL_CERT_PATH:-}"
    export SAVED_HTTPS_CA_BUNDLE="${HTTPS_CA_BUNDLE:-}"
    export SAVED_REQUESTS_CA_BUNDLE="${REQUESTS_CA_BUNDLE:-}"
}

# Clear SSL environment for system operations
clear_ssl_env() {
    unset CURL_CA_BUNDLE
    unset SSL_CERT_DIR
    unset SSL_CERT_FILE
    unset SSL_CERT_PATH
    # Also clear any other SSL-related env vars that might interfere
    unset HTTPS_CA_BUNDLE
    unset REQUESTS_CA_BUNDLE
}

# Restore SSL environment
restore_ssl_env() {
    [ -n "${SAVED_CURL_CA_BUNDLE:-}" ] && export CURL_CA_BUNDLE="$SAVED_CURL_CA_BUNDLE"
    [ -n "${SAVED_SSL_CERT_DIR:-}" ] && export SSL_CERT_DIR="$SAVED_SSL_CERT_DIR"
    [ -n "${SAVED_SSL_CERT_FILE:-}" ] && export SSL_CERT_FILE="$SAVED_SSL_CERT_FILE"
    [ -n "${SAVED_SSL_CERT_PATH:-}" ] && export SSL_CERT_PATH="$SAVED_SSL_CERT_PATH"
    [ -n "${SAVED_HTTPS_CA_BUNDLE:-}" ] && export HTTPS_CA_BUNDLE="$SAVED_HTTPS_CA_BUNDLE"
    [ -n "${SAVED_REQUESTS_CA_BUNDLE:-}" ] && export REQUESTS_CA_BUNDLE="$SAVED_REQUESTS_CA_BUNDLE"
    
    unset SAVED_CURL_CA_BUNDLE
    unset SAVED_SSL_CERT_DIR
    unset SAVED_SSL_CERT_FILE
    unset SAVED_SSL_CERT_PATH
    unset SAVED_HTTPS_CA_BUNDLE
    unset SAVED_REQUESTS_CA_BUNDLE
}

# Main function
main() {
    if [ $# -eq 0 ]; then
        print_error "Usage: $0 <make-target> [additional-args...]"
        print_info "Example: $0 db/install"
        print_info "Example: $0 db/create"
        exit 1
    fi

    local make_target="$1"
    shift

    # Check if Proxyman is interfering
    if is_proxyman_active; then
        print_warning "Proxyman SSL certificates detected, temporarily disabling for make operations..."
        save_ssl_env
        clear_ssl_env
    fi

    # Set up cleanup trap
    trap 'restore_ssl_env' EXIT INT TERM

    print_info "Running: make $make_target $*"
    
    # Run the make command
    if make "$make_target" "$@"; then
        print_info "Make command completed successfully"
        exit_code=0
    else
        print_error "Make command failed"
        exit_code=$?
    fi

    # Restore SSL environment (also done by trap)
    if is_proxyman_active; then
        restore_ssl_env
        print_info "Proxyman SSL certificates restored"
    fi

    exit $exit_code
}

# Run main function
main "$@"
