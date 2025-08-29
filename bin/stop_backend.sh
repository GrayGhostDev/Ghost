#!/bin/bash
# Ghost Backend Framework - Complete Backend Stop Script
# Gracefully shuts down the entire backend stack

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
log_step() { echo -e "${PURPLE}🛑 $1${NC}"; }

# Script header
echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║         Ghost Backend Framework - SHUTDOWN       ║"
echo "║              Complete Backend Stack               ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# =================================================================
# STEP 1: Stop Ghost Backend API Processes
# =================================================================
log_step "STEP 1: Stopping Ghost Backend API Processes"

# Find and stop Ghost Backend processes
ghost_pids=$(pgrep -f "simple_api.py\|uvicorn.*ghost\|python.*examples/simple_api.py" 2>/dev/null || true)
if [[ -n "$ghost_pids" ]]; then
    log_info "Found Ghost Backend processes: $ghost_pids"
    echo "$ghost_pids" | xargs kill -TERM 2>/dev/null || true
    sleep 3
    
    # Check if processes are still running
    ghost_pids=$(pgrep -f "simple_api.py\|uvicorn.*ghost\|python.*examples/simple_api.py" 2>/dev/null || true)
    if [[ -n "$ghost_pids" ]]; then
        log_warning "Force stopping Ghost Backend processes: $ghost_pids"
        echo "$ghost_pids" | xargs kill -9 2>/dev/null || true
    fi
    log_success "Ghost Backend processes stopped"
else
    log_info "No Ghost Backend processes found"
fi

# =================================================================
# STEP 2: Port Cleanup
# =================================================================
log_step "STEP 2: Port Cleanup"

cleanup_ports() {
    local ports=("8000" "8001")
    log_info "Cleaning up Ghost Backend ports: ${ports[*]}..."
    
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
            log_success "Port $port cleared"
        else
            log_info "Port $port is already free"
        fi
    done
}

cleanup_ports

# =================================================================
# STEP 3: Optional Service Cleanup
# =================================================================
log_step "STEP 3: Optional Service Cleanup"

# Ask user if they want to stop database services
echo ""
read -p "$(echo -e "${YELLOW}Do you want to stop PostgreSQL and Redis services? (y/N): ${NC}")" -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_step "Stopping Database Services"
    
    # Stop PostgreSQL
    log_info "Stopping PostgreSQL service..."
    if brew services list | grep postgresql | grep -q started; then
        if brew services stop postgresql@14 >/dev/null 2>&1 || brew services stop postgresql >/dev/null 2>&1; then
            log_success "PostgreSQL service stopped"
        else
            log_warning "Failed to stop PostgreSQL service (may not be managed by Homebrew)"
        fi
    else
        log_info "PostgreSQL service was not running"
    fi
    
    # Stop Redis
    log_info "Stopping Redis service..."
    if brew services list | grep redis | grep -q started; then
        if brew services stop redis >/dev/null 2>&1; then
            log_success "Redis service stopped"
        else
            log_warning "Failed to stop Redis service (may not be managed by Homebrew)"
        fi
    else
        log_info "Redis service was not running"
    fi
else
    log_info "Database services left running (recommended for development)"
fi

# =================================================================
# STEP 4: Cleanup Runtime Files
# =================================================================
log_step "STEP 4: Cleanup Runtime Files"

# Remove runtime environment file (for security)
if [[ -f ".env.runtime" ]]; then
    rm -f .env.runtime
    log_success "Runtime environment file removed"
fi

# Clean up temporary files
if [[ -d "__pycache__" ]]; then
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    log_success "Python cache files cleaned"
fi

# Clean up log files if requested
echo ""
read -p "$(echo -e "${YELLOW}Do you want to clean log files? (y/N): ${NC}")" -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [[ -d "logs" ]]; then
        rm -rf logs/*.log 2>/dev/null || true
        log_success "Log files cleaned"
    fi
fi

# =================================================================
# STEP 5: Verification
# =================================================================
log_step "STEP 5: Shutdown Verification"

# Check ports are free
ports_clear=true
for port in 8000 8001; do
    if lsof -i :$port >/dev/null 2>&1; then
        log_error "Port $port is still in use"
        ports_clear=false
    else
        log_success "Port $port is free"
    fi
done

# Check processes
ghost_processes=$(pgrep -f "simple_api.py\|uvicorn.*ghost\|python.*examples/simple_api.py" 2>/dev/null || true)
if [[ -n "$ghost_processes" ]]; then
    log_error "Ghost Backend processes still running: $ghost_processes"
    ports_clear=false
else
    log_success "No Ghost Backend processes running"
fi

# Final status
echo ""
if $ports_clear; then
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════════════════╗"
    echo "║            🛑 BACKEND STOPPED 🛑                 ║"
    echo "╠═══════════════════════════════════════════════════╣"
    echo "║ ✅ All Ghost Backend processes stopped           ║"
    echo "║ ✅ All ports cleared (8000, 8001)               ║"
    echo "║ ✅ Runtime files cleaned                         ║"
    echo "║ ✅ System ready for restart                      ║"
    echo "╚═══════════════════════════════════════════════════╝"
    echo -e "${NC}"
    log_success "Ghost Backend shutdown complete"
else
    echo -e "${RED}"
    echo "╔═══════════════════════════════════════════════════╗"
    echo "║            ⚠️  SHUTDOWN ISSUES ⚠️                ║"
    echo "╠═══════════════════════════════════════════════════╣"
    echo "║ Some processes may still be running              ║"
    echo "║ Check the errors above and resolve manually      ║"
    echo "║ You may need to restart your terminal/system     ║"
    echo "╚═══════════════════════════════════════════════════╝"
    echo -e "${NC}"
    exit 1
fi
