#!/bin/bash
# Ghost Backend API Runner Script - Port 8001 variant
# For running on alternate dedicated port

cd "$(dirname "$0")"

# Override API_PORT to use 8001
export API_PORT=8001

echo "🔄 Starting Ghost Backend on alternate dedicated port 8001..."
exec ./run_api.sh
