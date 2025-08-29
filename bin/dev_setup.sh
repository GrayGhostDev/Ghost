#!/bin/bash

#!/bin/bash
# Ghost Backend Framework - Development Environment Setup
# Secure version using keychain-stored credentials

set -euo pipefail

echo "🔧 Setting up Ghost Backend development environment..."

# Setup Python virtual environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Install development dependencies
echo "📋 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements-dev.txt

# Setup secure credentials
echo "🔐 Setting up secure credentials..."
if [ ! -f ".env.runtime" ]; then
    if [ -f "scripts/secrets/keychain.sh" ]; then
        echo "⚙️  Running keychain setup..."
        ./scripts/secrets/keychain.sh setup
        ./scripts/secrets/keychain.sh runtime-env
    else
        echo "⚠️  Keychain script not found. You may need to manually setup credentials."
    fi
else
    echo "✅ Runtime environment already configured"
fi

# Create necessary directories
echo "� Creating project directories..."
mkdir -p logs uploads migrations/versions

# Set up database
echo "�️  Setting up database..."
if command -v createdb >/dev/null 2>&1; then
    createdb ghost 2>/dev/null || echo "Database 'ghost' already exists or createdb not available"
else
    echo "⚠️  createdb not found. Please ensure PostgreSQL is installed."
fi

echo "✅ Development environment setup complete!"
echo ""
echo "🚀 To start the API server:"
echo "   ./run_api.sh"
echo ""
echo "🔐 To manage credentials:"
echo "   ./scripts/secrets/keychain.sh list"
