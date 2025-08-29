#!/usr/bin/env python3
"""
Ghost Backend Framework - Complete Development Integration Setup

This script completes the backend installation by adding missing components
and ensuring full development integration capability.
"""

import os
import sys
import subprocess
from pathlib import Path
import yaml

from typing import Optional

def run_command(command: str, description: Optional[str] = None):
    """Run a shell command and handle errors."""
    if description:
        print(f"🔧 {description}...")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ Success")
            if result.stdout.strip():
                print(f"  📝 {result.stdout.strip()}")
        else:
            print(f"  ❌ Failed: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    return True


def install_redis():
    """Install and configure Redis."""
    print("\n📦 Installing Redis...")
    
    # Check if Redis is already installed
    if run_command("redis-cli ping", "Checking Redis installation"):
        print("  ✅ Redis is already installed and running")
        return True
    
    # Install Redis via Homebrew
    if not run_command("brew install redis", "Installing Redis via Homebrew"):
        return False
    
    # Start Redis service
    if not run_command("brew services start redis", "Starting Redis service"):
        return False
    
    # Test Redis connection
    if run_command("redis-cli ping", "Testing Redis connection"):
        print("  ✅ Redis installation completed successfully")
        return True
    
    return False


def install_missing_packages():
    """Install missing Python packages."""
    print("\n📦 Installing missing Python packages...")
    
    missing_packages = [
        "celery[redis]",  # Background task processing
        "watchdog",       # File system monitoring  
        "python-multipart",  # File upload support
        "email-validator",   # Email validation
        "python-jose[cryptography]",  # JWT token handling
        "passlib[bcrypt]",   # Password hashing
    ]
    
    for package in missing_packages:
        if not run_command(f"pip install {package}", f"Installing {package}"):
            print(f"  ⚠️  Failed to install {package}")
    
    print("  ✅ Package installation completed")
    return True


def fix_configuration_issues():
    """Fix configuration class issues."""
    print("\n🔧 Fixing configuration issues...")
    
    config_file = Path(__file__).parent.parent / "src" / "ghost" / "config.py"
    
    # Read the current config file
    with open(config_file, 'r') as f:
        content = f.read()
    
    # Add AuthConfig class if missing
    if "class AuthConfig:" not in content:
        auth_config = '''
@dataclass
class AuthConfig:
    """Authentication configuration settings."""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 8
'''
        
        # Insert after ExternalAPIsConfig
        content = content.replace(
            "class Config:",
            f"{auth_config}\n\n@dataclass\nclass Config:"
        )
        
        # Add auth field to Config class
        content = content.replace(
            "external_apis: ExternalAPIsConfig = field(default_factory=ExternalAPIsConfig)",
            "external_apis: ExternalAPIsConfig = field(default_factory=ExternalAPIsConfig)\n    auth: AuthConfig = field(default_factory=AuthConfig)"
        )
        
        with open(config_file, 'w') as f:
            f.write(content)
        
        print("  ✅ Added AuthConfig to configuration")
    
    return True


def setup_database_migrations():
    """Set up database migrations and seed data."""
    print("\n🗄️ Setting up database migrations...")
    
    # Create migrations directory
    migrations_dir = Path(__file__).parent.parent / "migrations"
    migrations_dir.mkdir(exist_ok=True)
    
    # Run migrations
    migration_script = Path(__file__).parent / "database_migrations.py"
    
    if migration_script.exists():
        if run_command(f"python {migration_script} migrate", "Running database migrations"):
            run_command(f"python {migration_script} seed", "Seeding development data")
            print("  ✅ Database setup completed")
            return True
    
    return False


def create_docker_development_setup():
    """Create Docker development environment files."""
    print("\n🐳 Creating Docker development setup...")
    
    base_dir = Path(__file__).parent.parent
    
    # Create Dockerfile
    dockerfile_content = """FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    postgresql-client \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy application code
COPY . .

# Install the package in development mode
RUN pip install -e .

# Expose port
EXPOSE 8888

# Default command
CMD ["python", "tools/start_multi_backend.py"]
"""
    
    with open(base_dir / "Dockerfile", 'w') as f:
        f.write(dockerfile_content)
    
    # Create docker-compose.yml
    compose_content = """version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8888:8888"
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - API_KEY=${API_KEY}
      - DB_HOST=postgres
      - REDIS_HOST=redis
      - ANTHROPIC_ADMIN_API_KEY=${ANTHROPIC_ADMIN_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GITHUB_PAT=${GITHUB_PAT}
      - BRAVE_API_KEY=${BRAVE_API_KEY}
    depends_on:
      - postgres
      - redis
    volumes:
      - .:/app
      - /app/.venv
    
  postgres:
    image: postgres:16
    environment:
      - POSTGRES_DB=ghost
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=ghost_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
"""
    
    with open(base_dir / "docker-compose.yml", 'w') as f:
        f.write(compose_content)
    
    print("  ✅ Docker setup files created")
    return True


def create_development_scripts():
    """Create helpful development scripts."""
    print("\n📝 Creating development scripts...")
    
    base_dir = Path(__file__).parent.parent
    
    # Create dev setup script
    dev_setup_script = """#!/bin/bash

# Ghost Backend Development Setup Script
echo "🏁 Setting up Ghost Backend for development..."

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Set up environment variables from keychain
source .env.runtime  # Load secure credentials from keychain

# Run migrations
python tools/scripts/database_migrations.py migrate
python tools/scripts/database_migrations.py seed

# Start services
echo "🚀 Starting development services..."
echo "📡 Backend will be available at: http://localhost:8888"
echo "📚 API docs will be available at: http://localhost:8888/docs"

# Start the backend
python tools/start_multi_backend.py
"""
    
    with open(base_dir / "dev_setup.sh", 'w') as f:
        f.write(dev_setup_script)
    
    # Make it executable
    os.chmod(base_dir / "dev_setup.sh", 0o755)
    
    print("  ✅ Development scripts created")
    return True


def run_tests_and_verify():
    """Run tests to verify installation completeness."""
    print("\n🧪 Running verification tests...")
    
    # Run basic connectivity tests
    tests_passed = 0
    total_tests = 4
    
    # Test 1: Redis connectivity
    if run_command("redis-cli ping", "Testing Redis"):
        tests_passed += 1
    
    # Test 2: Database connectivity  
    if run_command("python -c 'from ghost.database import get_db_manager; get_db_manager().initialize(); print(\"Database OK\")'", "Testing database"):
        tests_passed += 1
    
    # Test 3: Configuration loading
    if run_command("python -c 'from ghost.config import get_config; config = get_config(); print(f\"Config loaded: {config.project_name}\")'", "Testing configuration"):
        tests_passed += 1
    
    # Test 4: Frontend detection
    if run_command("python tools/scripts/frontend_detector.py --scan-dirs . --config-file test-config.yaml", "Testing frontend detection"):
        tests_passed += 1
    
    print(f"\n📊 Verification Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("  ✅ All verification tests passed!")
        return True
    else:
        print("  ⚠️  Some tests failed - check the output above")
        return False


def main():
    """Main setup function."""
    print("🔧 Ghost Backend Framework - Complete Development Integration Setup")
    print("=" * 70)
    
    # Step 1: Install Redis
    install_redis()
    
    # Step 2: Install missing Python packages
    install_missing_packages()
    
    # Step 3: Fix configuration issues
    fix_configuration_issues()
    
    # Step 4: Set up database migrations
    setup_database_migrations()
    
    # Step 5: Create Docker setup
    create_docker_development_setup()
    
    # Step 6: Create development scripts
    create_development_scripts()
    
    # Step 7: Run verification tests
    verification_passed = run_tests_and_verify()
    
    print("\n" + "=" * 70)
    print("🎉 Ghost Backend Framework Setup Complete!")
    print("=" * 70)
    
    if verification_passed:
        print("\n✅ All components successfully installed and verified!")
        print("\n🚀 Quick Start Commands:")
        print("   • Start development: ./dev_setup.sh")
        print("   • Start with Docker: docker-compose up")
        print("   • Run migrations: python tools/scripts/database_migrations.py migrate")
        print("   • Detect frontends: python tools/scripts/frontend_detector.py")
        print("   • Run tests: python -m pytest tests/")
        
        print("\n📡 Access Points:")
        print("   • API Server: http://localhost:8888")
        print("   • API Documentation: http://localhost:8888/docs")
        print("   • WebSocket: ws://localhost:8888/ws/[frontend_type]")
        
        print("\n👥 Development Accounts:")
        print("   • Admin: admin / admin123")
        print("   • Test User: testuser / test123")
    else:
        print("\n⚠️  Setup completed with some issues. Review the output above.")
        print("   Some components may need manual configuration.")
    
    print("\n📚 Documentation available in: docs/")
    print("💡 For help: Check README.md or run with --help")


if __name__ == "__main__":
    main()
