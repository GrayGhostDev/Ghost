#!/bin/bash
# Ghost Backend - Stop All Instances
# Cleanly stops all Ghost Backend API processes

echo "🛑 Stopping all Ghost Backend API instances..."

# Find and kill processes on ports 8000 and 8001
echo "  🔍 Checking port 8000..."
PORT_8000_PIDS=$(lsof -ti :8000 2>/dev/null || true)
if [[ -n "$PORT_8000_PIDS" ]]; then
    echo "  ⏹️  Stopping processes on port 8000: $PORT_8000_PIDS"
    echo "$PORT_8000_PIDS" | xargs kill -TERM 2>/dev/null || true
    sleep 2
    # Force kill if still running
    PORT_8000_PIDS=$(lsof -ti :8000 2>/dev/null || true)
    if [[ -n "$PORT_8000_PIDS" ]]; then
        echo "  🔨 Force stopping processes on port 8000: $PORT_8000_PIDS"
        echo "$PORT_8000_PIDS" | xargs kill -9 2>/dev/null || true
    fi
else
    echo "  ✅ No processes on port 8000"
fi

echo "  🔍 Checking port 8001..."
PORT_8001_PIDS=$(lsof -ti :8001 2>/dev/null || true)
if [[ -n "$PORT_8001_PIDS" ]]; then
    echo "  ⏹️  Stopping processes on port 8001: $PORT_8001_PIDS"
    echo "$PORT_8001_PIDS" | xargs kill -TERM 2>/dev/null || true
    sleep 2
    # Force kill if still running
    PORT_8001_PIDS=$(lsof -ti :8001 2>/dev/null || true)
    if [[ -n "$PORT_8001_PIDS" ]]; then
        echo "  🔨 Force stopping processes on port 8001: $PORT_8001_PIDS"
        echo "$PORT_8001_PIDS" | xargs kill -9 2>/dev/null || true
    fi
else
    echo "  ✅ No processes on port 8001"
fi

echo "✅ All Ghost Backend instances stopped"
echo "🔓 Ports 8000 and 8001 are now available"
