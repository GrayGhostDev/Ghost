#!/bin/bash
# Ghost Backend Framework - Complete Backend Startup Script
# Handles the entire backend startup workflow with all dependencies

set -euo pipefail

# Change to project root directory (parent of bin/)
cd "$(dirname "$0")/.."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Logging functions
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_step() { echo -e "${PURPLE}🚀 $1${NC}"; }

# Script header
echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║         Ghost Backend Framework - STARTUP        ║"
echo "║              Complete Backend Stack               ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# Configuration
API_PORT="${API_PORT:-8000}"
DB_PORT="${DB_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"

# =================================================================
# STEP 1: Port Cleanup and Management
# =================================================================
log_step "STEP 1: Port Cleanup and Management"

cleanup_ports() {
    local ports=("8000" "8001")
    log_info "Cleaning up ports: ${ports[*]}..."
    
    for port in "${ports[@]}"; do
        local pids
        pids=$(lsof -ti :$port 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            log_warning "Stopping processes on port $port: $pids"
            echo "$pids" | xargs kill -TERM 2>/dev/null || true
            sleep 2
            # Force kill if still running
            pids=$(lsof -ti :$port 2>/dev/null || true)
            if [[ -n "$pids" ]]; then
                log_warning "Force stopping processes on port $port: $pids"
                echo "$pids" | xargs kill -9 2>/dev/null || true
            fi
        fi
    done
    
    log_success "API ports cleared and ready"
}

cleanup_ports

# =================================================================
# STEP 2: Security and Credentials Setup
# =================================================================
log_step "STEP 2: Security and Credentials Setup"

# Check keychain setup
if ! ./tools/security/keychain.sh list >/dev/null 2>&1; then
    log_warning "Keychain not properly set up. Initializing..."
    ./tools/security/keychain.sh setup
    log_success "Keychain credentials initialized"
else
    log_success "Keychain credentials verified"
fi

# Generate/update runtime environment
log_info "Generating secure runtime environment..."
./tools/security/keychain.sh runtime-env
log_success "Runtime environment ready"

# Source runtime environment
if [[ -f ".env.runtime" ]]; then
    source .env.runtime
    log_success "Runtime environment loaded"
else
    log_error "Runtime environment file not found!"
    exit 1
fi

# Verify critical credentials
for var in JWT_SECRET API_KEY SECRET_KEY; do
    if [[ -z "${!var:-}" ]]; then
        log_error "$var not loaded from keychain"
        exit 1
    fi
done
log_success "All credentials verified and loaded"

# =================================================================
# STEP 3: Virtual Environment Setup
# =================================================================
log_step "STEP 3: Virtual Environment Setup"

if [[ ! -d ".venv" ]]; then
    log_warning "Virtual environment not found. Creating..."
    python3 -m venv .venv
    log_success "Virtual environment created"
fi

log_info "Activating virtual environment..."
source .venv/bin/activate
log_success "Virtual environment activated"

# Install/update dependencies
if [[ ! -f ".venv/deps_installed" ]] || [[ "requirements.txt" -nt ".venv/deps_installed" ]]; then
    log_info "Installing/updating Python dependencies..."
    pip install --upgrade pip >/dev/null 2>&1
    pip install -r requirements.txt >/dev/null 2>&1
    pip install -r requirements-dev.txt >/dev/null 2>&1
    touch .venv/deps_installed
    log_success "Dependencies installed/updated"
else
    log_success "Dependencies up to date"
fi

# =================================================================
# STEP 4: Database Services Setup
# =================================================================
log_step "STEP 4: Database Services Setup"

# Check PostgreSQL
log_info "Checking PostgreSQL service..."
if brew services list | grep postgresql@14 | grep -q started; then
    log_success "PostgreSQL service is running"
elif brew services list | grep postgresql | grep -q started; then
    log_success "PostgreSQL service is running"
else
    log_warning "PostgreSQL not running. Starting service..."
    if command -v brew >/dev/null; then
        if brew services start postgresql@14 >/dev/null 2>&1 || brew services start postgresql >/dev/null 2>&1; then
            log_success "PostgreSQL service started"
            sleep 3  # Give it time to start
        else
            log_error "Failed to start PostgreSQL service"
            exit 1
        fi
    else
        log_error "PostgreSQL not running and Homebrew not available"
        exit 1
    fi
fi

# Test database connection
log_info "Testing database connection..."
if timeout 5 pg_isready -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" >/dev/null 2>&1; then
    log_success "Database connection verified"
else
    log_error "Cannot connect to database at ${DB_HOST:-localhost}:${DB_PORT:-5432}"
    log_warning "Make sure PostgreSQL is running and accessible"
    exit 1
fi

# Database setup and migrations
log_info "Setting up database..."
if python scripts/database_migrations.py create-tables >/dev/null 2>&1; then
    log_success "Database tables ready"
else
    log_warning "Database tables may already exist (this is normal)"
fi

# =================================================================
# STEP 5: Redis Setup
# =================================================================
log_step "STEP 5: Redis Setup"

log_info "Checking Redis service..."
if redis-cli ping >/dev/null 2>&1; then
    log_success "Redis service is running"
else
    log_warning "Redis not running. Starting service..."
    if command -v brew >/dev/null; then
        if brew services start redis >/dev/null 2>&1; then
            log_success "Redis service started"
            sleep 2  # Give it time to start
            if ! redis-cli ping >/dev/null 2>&1; then
                log_error "Redis failed to start properly"
                exit 1
            fi
        else
            log_error "Failed to start Redis service"
            exit 1
        fi
    else
        log_error "Redis not running and Homebrew not available"
        exit 1
    fi
fi

# =================================================================
# STEP 6: Directory and Log Setup
# =================================================================
log_step "STEP 6: Directory and Log Setup"

# Create necessary directories
for dir in logs uploads backups; do
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        log_info "Created directory: $dir"
    fi
done
log_success "Directory structure verified"

# =================================================================
# STEP 7: Final System Validation
# =================================================================
log_step "STEP 7: System Validation"

# Check all services
services_ok=true

# Check ports availability
for port in 8000 8001; do
    if lsof -i :$port >/dev/null 2>&1; then
        log_error "Port $port is still in use"
        services_ok=false
    fi
done

# Final service checks
if ! pg_isready -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" >/dev/null 2>&1; then
    log_error "Database connection failed"
    services_ok=false
fi

if ! redis-cli ping >/dev/null 2>&1; then
    log_error "Redis connection failed"
    services_ok=false
fi

if ! $services_ok; then
    log_error "Pre-flight checks failed. Please resolve issues above."
    exit 1
fi

log_success "All systems ready for launch"

# =================================================================
# STEP 8: Launch Ghost Backend API
# =================================================================
log_step "STEP 8: Launching Ghost Backend API"

# Set environment variables
export API_PORT="$API_PORT"
export API_HOST="${API_HOST:-127.0.0.1}"  # Default to localhost for security, can be overridden

# Trap for clean shutdown
cleanup_on_exit() {
    log_warning "Shutting down Ghost Backend..."
    # Kill any remaining processes
    for port in 8000 8001; do
        local pids
        pids=$(lsof -ti :$port 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            echo "$pids" | xargs kill -TERM 2>/dev/null || true
        fi
    done
    exit 0
}

trap cleanup_on_exit INT TERM

# Final status display
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║              🚀 BACKEND STARTING 🚀              ║"
echo "╠═══════════════════════════════════════════════════╣"
echo "║ Host: $API_HOST"
echo "║ Port: $API_PORT (EXCLUSIVE ACCESS)"
echo "║ Database: ${DB_HOST:-localhost}:${DB_PORT:-5432}/${DB_NAME:-ghost_db}"
echo "║ Redis: localhost:${REDIS_PORT:-6379}"
echo "║ Environment: ${ENVIRONMENT:-development}"
echo "║ Debug: ${DEBUG:-false}"
echo "║ Security: ✅ Keychain Secured"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

log_info "Starting Ghost Backend API server..."
echo ""

# Launch the API server
python examples/simple_api.py
