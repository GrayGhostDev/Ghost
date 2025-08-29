#!/bin/bash
# Ghost Backend Framework - Security Verification Script
# Verifies that all credentials have been properly secured

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

echo "🔍 Ghost Backend Framework - Security Verification"
echo "================================================="

# Check for exposed secrets in codebase
log_info "Checking for exposed secrets in codebase..."

# Test for each secret pattern individually 
SECRETS_FOUND=false

# Check specific exposed secrets
for secret in "sk-ant-admin01" "ghp_qYDj7StKx" "BSAQRnhgYzC94_lX5bxwG" "dT21J7SNrklcgafpPGU31m" "Xk8zjMwOFiwvhUGPWA0fgG"; do
    if grep -r "$secret" --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=htmlcov --exclude-dir=__pycache__ --exclude="*.md" --exclude="*.INSECURE" --exclude="*.example" --exclude="*.template" --exclude="verify_security.sh" . > /dev/null 2>&1; then
        log_error "Exposed secret found: $secret"
        SECRETS_FOUND=true
    fi
done

if ! $SECRETS_FOUND; then
    log_success "No exposed secrets found in codebase"
fi

# Check keychain setup
log_info "Checking keychain integration..."
if [[ -f "scripts/secrets/keychain.sh" ]]; then
    log_success "Keychain management script found"
    
    if ./scripts/secrets/keychain.sh list > /dev/null 2>&1; then
        log_success "Keychain integration is working"
    else
        log_warning "Keychain integration needs setup"
        log_info "Run: ./scripts/secrets/keychain.sh setup"
    fi
else
    log_error "Keychain management script not found"
fi

# Check runtime environment
log_info "Checking runtime environment..."
if [[ -f ".env.runtime" ]]; then
    log_success "Runtime environment file exists"
    
    # Test if it can load credentials (without showing them)
    if source .env.runtime && [[ -n "${JWT_SECRET:-}" ]] && [[ -n "${API_KEY:-}" ]]; then
        log_success "Runtime environment loads credentials successfully"
    else
        log_warning "Runtime environment exists but doesn't load all credentials"
        log_info "Run: ./scripts/secrets/keychain.sh runtime-env"
    fi
else
    log_warning "Runtime environment file not found"
    log_info "Run: ./scripts/secrets/keychain.sh runtime-env"
fi

# Check secure configuration files
log_info "Checking configuration files..."
config_files=("config.production.yaml" "docker-compose.yml" "run_api.sh" "tools/start_multi_backend.py")

for file in "${config_files[@]}"; do
    if [[ -f "$file" ]]; then
        if grep -E '\$\{[A-Z_]+\}|os\.environ\.get|source \.env\.runtime' "$file" > /dev/null 2>&1; then
            log_success "$file uses secure environment variable references"
        else
            log_warning "$file may not be using secure credential references"
        fi
    else
        log_info "$file not found (may be optional)"
    fi
done

# Check git ignore
log_info "Checking git ignore configuration..."
if grep -E "\.env\.runtime|\.env\.backup|\.INSECURE" .gitignore > /dev/null 2>&1; then
    log_success "Git ignore properly configured for security files"
else
    log_warning "Git ignore may not be properly configured"
    log_info "Ensure .env.runtime and .env.backup.* are in .gitignore"
fi

# Check for insecure backup files
log_info "Checking for insecure backup files..."
if find . -name "*.INSECURE" -o -name ".env.backup.*" | grep -q .; then
    log_warning "Insecure backup files found - ensure these are git ignored"
    find . -name "*.INSECURE" -o -name ".env.backup.*"
else
    log_success "No insecure backup files found"
fi

echo ""
echo "🛡️  Security Verification Complete"
echo "=================================="

# Final recommendation
if ! $SECRETS_FOUND && ./scripts/secrets/keychain.sh list > /dev/null 2>&1 && [[ -f ".env.runtime" ]]; then
    log_success "Your Ghost Backend Framework is properly secured!"
    echo ""
    log_info "To start your application securely:"
    echo "   ./run_api.sh"
    echo ""
    log_warning "IMPORTANT: Remember to revoke the exposed API keys listed in SECURITY_REMEDIATION_REPORT.md"
    exit 0
else
    echo ""
    log_error "Security verification failed!"
    if $SECRETS_FOUND; then
        log_error "Exposed secrets found in codebase"
    fi
    if ! ./scripts/secrets/keychain.sh list > /dev/null 2>&1; then
        log_warning "Keychain integration not working"
    fi
    if [[ ! -f ".env.runtime" ]]; then
        log_warning "Runtime environment file missing"
    fi
    echo ""
    log_warning "Follow these steps to fix security issues:"
    echo "   1. ./scripts/secrets/keychain.sh setup"
    echo "   2. ./scripts/secrets/keychain.sh runtime-env" 
    echo "   3. ./run_api.sh"
    echo "   4. Revoke exposed keys (see SECURITY_REMEDIATION_REPORT.md)"
    exit 1
fi
