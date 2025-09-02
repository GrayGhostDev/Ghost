#!/bin/bash
# Ghost Backend API Runner Script
# Secure version using keychain-stored credentials

cd "$(dirname "$0")"

# Function to clean up ports
cleanup_ports() {
    echo "🧹 Cleaning up ports 8000 and 8001..."
    
    # Find and kill processes on port 8000
    PORT_8000_PIDS=$(lsof -ti :8000 2>/dev/null || true)
    if [[ -n "$PORT_8000_PIDS" ]]; then
        echo "  🔧 Stopping processes on port 8000: $PORT_8000_PIDS"
        echo "$PORT_8000_PIDS" | xargs kill -9 2>/dev/null || true
    fi
    
    # Find and kill processes on port 8001
    PORT_8001_PIDS=$(lsof -ti :8001 2>/dev/null || true)
    if [[ -n "$PORT_8001_PIDS" ]]; then
        echo "  🔧 Stopping processes on port 8001: $PORT_8001_PIDS"
        echo "$PORT_8001_PIDS" | xargs kill -9 2>/dev/null || true
    fi
    
    # Wait a moment for cleanup
    sleep 2
    
    echo "✅ Ports 8000 and 8001 are now available exclusively for Ghost Backend"
}

# Clean up ports before starting
cleanup_ports

# Source runtime environment from keychain
if [[ -f ".env.runtime" ]]; then
    source .env.runtime
else
    echo "⚠️  Runtime environment not found. Run: ./scripts/secrets/keychain.sh setup"
    exit 1
fi

# Verify critical environment variables are loaded
if [[ -z "${JWT_SECRET:-}" ]]; then
    echo "❌ JWT_SECRET not loaded from keychain"
    exit 1
fi

if [[ -z "${API_KEY:-}" ]]; then
    echo "❌ API_KEY not loaded from keychain"
    exit 1
fi

echo "✅ Credentials loaded securely from keychain"

# Set trap to clean up on exit
trap 'echo "🛑 Shutting down Ghost Backend API..."; exit 0' INT TERM

# Activate virtual environment
source .venv/bin/activate

# Set API port from environment or use default
export API_PORT="${API_PORT:-8000}"

echo "🚀 Starting Ghost Backend API (Dedicated Server)..."
echo "📡 Host: ${API_HOST:-127.0.0.1}"
echo "📡 Port: $API_PORT (EXCLUSIVE ACCESS)"
echo "🔑 JWT Secret loaded from keychain"
echo "🗄️  Database: ${DB_HOST:-localhost}:${DB_PORT:-5432}/${DB_NAME:-ghost_db}"
echo "🔒 This port is dedicated exclusively to Ghost Backend"
echo ""

# Run the API
python examples/simple_api.py
