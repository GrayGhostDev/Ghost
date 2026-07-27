#!/usr/bin/env python3
"""
Docker Entrypoint for Ghost Backend Framework

This script handles container startup without relying on macOS keychain.
Environment variables should be provided via docker-compose or Docker secrets.
"""

import os
import socket
import sys
import time
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, '/app/src')

# Retries start here and double up to this ceiling. A flat 2s interval burned
# the whole budget in 60s and then exited, which under `restart: unless-stopped`
# becomes an unbounded crash loop.
BACKOFF_START = 2
BACKOFF_MAX = 30


def _backoff(attempt, start=BACKOFF_START, ceiling=BACKOFF_MAX):
    """Exponential backoff for `attempt` (0-indexed), capped at `ceiling`."""
    return min(start * (2 ** attempt), ceiling)


def _describe_host(host):
    """Resolve `host` so a DNS failure reads differently from a refused connection.

    A detached container (no network endpoint) and a container that is merely
    still booting both surface as 'not ready'; only the resolver tells them
    apart, and that distinction is the whole diagnosis.
    """
    try:
        return f"{host} -> {socket.gethostbyname(host)}"
    except socket.gaierror as e:
        return f"{host} -> DNS FAILURE ({e.strerror or e})"


def wait_for_database(max_retries=None, retry_interval=None):
    """Wait for PostgreSQL to be ready."""
    if max_retries is None:
        max_retries = int(os.environ.get('MAX_DB_RETRIES', '30'))
    db_host = os.environ.get('DB_HOST', 'postgres')
    db_port = os.environ.get('DB_PORT', '5432')
    db_user = os.environ.get('DB_USER', 'postgres')

    print(f"🔄 Waiting for PostgreSQL at {db_host}:{db_port}...")

    for i in range(max_retries):
        try:
            result = subprocess.run(
                ['pg_isready', '-h', db_host, '-p', db_port, '-U', db_user],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print("✅ PostgreSQL is ready!")
                return True
        except subprocess.TimeoutExpired:
            pass

        if i < max_retries - 1:
            delay = retry_interval if retry_interval is not None else _backoff(i)
            print(f"  Attempt {i+1}/{max_retries} failed ({_describe_host(db_host)}), "
                  f"retrying in {delay}s...")
            time.sleep(delay)

    print(f"❌ PostgreSQL not available after {max_retries} attempts: {_describe_host(db_host)}")
    return False

def wait_for_redis(max_retries=None, retry_interval=None):
    """Wait for Redis to be ready."""
    if max_retries is None:
        max_retries = int(os.environ.get('MAX_REDIS_RETRIES', '30'))
    redis_host = os.environ.get('REDIS_HOST', 'redis')
    redis_port = os.environ.get('REDIS_PORT', '6379')
    # Compose starts Redis with --requirepass. Connecting without the password
    # made every PING raise AuthenticationError, which subclasses ConnectionError
    # and so was silently swallowed as "not ready" — the container burned the
    # full retry budget and logged a false outage against a healthy Redis.
    redis_password = os.environ.get('REDIS_PASSWORD') or None

    print(f"🔄 Waiting for Redis at {redis_host}:{redis_port}...")

    # Import here to avoid issues if redis isn't installed
    try:
        import redis
    except ImportError:
        print("⚠️  Redis client not installed, skipping Redis check")
        return True

    r = redis.Redis(
        host=redis_host,
        port=int(redis_port),
        password=redis_password,
        socket_connect_timeout=5,
    )

    for i in range(max_retries):
        try:
            if r.ping():
                print("✅ Redis is ready!")
                return True
        except redis.AuthenticationError as e:
            # Not a readiness problem — retrying cannot fix a wrong password.
            print(f"❌ Redis authentication failed: {e}")
            print("   Check REDIS_PASSWORD against the --requirepass in docker-compose.yml")
            return False
        except (redis.ConnectionError, redis.TimeoutError):
            pass

        if i < max_retries - 1:
            delay = retry_interval if retry_interval is not None else _backoff(i)
            print(f"  Attempt {i+1}/{max_retries} failed ({_describe_host(redis_host)}), "
                  f"retrying in {delay}s...")
            time.sleep(delay)

    print(f"❌ Redis not available after {max_retries} attempts: {_describe_host(redis_host)}")
    return False

def run_migrations():
    """Run database migrations if alembic is configured."""
    alembic_ini = Path('/app/alembic.ini')
    if not alembic_ini.exists():
        print("ℹ️  No alembic.ini found, skipping migrations")
        return True

    # Allow disabling migrations via env var (e.g. for testing)
    if os.environ.get('SKIP_MIGRATIONS', '').lower() in ('true', '1', 'yes'):
        print("⚠️  Migrations skipped (SKIP_MIGRATIONS=true)")
        return True

    print("🔄 Running database migrations...")
    try:
        result = subprocess.run(
            ['alembic', 'upgrade', 'head'],
            capture_output=True,
            text=True,
            cwd='/app'
        )
        if result.returncode == 0:
            print("✅ Migrations completed successfully")
            return True
        else:
            print(f"⚠️  Migration failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("⚠️  Alembic not installed, skipping migrations")
        return True

def create_test_app():
    """Create a minimal test FastAPI application."""
    test_app_code = '''
from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="Ghost Backend Test")

@app.get("/")
def root():
    return {"message": "Ghost Backend is running!", "timestamp": datetime.now().isoformat()}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "ghost-backend"}
'''
    
    # Write the test app
    with open('/tmp/test_app.py', 'w') as f:
        f.write(test_app_code)
    
    return 'test_app:app'

def validate_environment():
    """Validate required environment variables.

    Outside development the secrets are mandatory: `required_vars` used to be an
    empty list, so a container booting with no JWT_SECRET fell through to the
    framework's built-in default and served traffic signed with a known key.
    """
    environment = os.environ.get('ENVIRONMENT', 'development').lower()
    secrets = ['JWT_SECRET', 'API_KEY', 'DB_PASSWORD']

    if environment in ('development', 'dev', 'test', 'docker'):
        required_vars, recommended_vars = [], secrets
    else:
        required_vars, recommended_vars = secrets, []

    missing_required = [var for var in required_vars if not os.environ.get(var)]
    missing_recommended = [var for var in recommended_vars if not os.environ.get(var)]

    if missing_required:
        print(f"❌ Missing required environment variables for ENVIRONMENT={environment}: "
              f"{', '.join(missing_required)}")
        return False

    if missing_recommended:
        print(f"⚠️  Missing recommended environment variables: {', '.join(missing_recommended)}")
        print("   Using default values - NOT suitable for production!")

    return True

def start_application():
    """Start the FastAPI application."""
    import uvicorn
    
    # Add paths to Python path
    sys.path.insert(0, '/app')
    sys.path.insert(0, '/tmp')
    
    try:
        from ghost import get_config
        config = get_config()
    except ImportError:
        print("⚠️  Ghost module not fully configured, using defaults")
        config = None
    
    # Determine the application module
    # Check if examples module exists, otherwise use a simple test app
    examples_path = Path('/app/examples/simple_api.py')
    if examples_path.exists():
        print("✅ Found examples/simple_api.py")
        app_module = os.environ.get('APP_MODULE', 'examples.simple_api:app')
    else:
        # Create a minimal test application
        print("⚠️  Examples module not found, creating minimal test app...")
        app_module = create_test_app()
    
    # Get host and port from environment or config
    # Cloud Run sets $PORT at runtime; fall back to API_PORT or 8801
    host = os.environ.get('API_HOST', '0.0.0.0')  # 0.0.0.0 is OK inside container
    port = int(os.environ.get('PORT', os.environ.get('API_PORT', '8801')))
    workers = int(os.environ.get('WORKERS', '1'))
    
    print(f"""
🚀 Starting Ghost Backend Framework
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 Environment: {os.environ.get('ENVIRONMENT', 'docker')}
🌐 Host: {host}
🔌 Port: {port}
👷 Workers: {workers}
📱 App: {app_module}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    if workers > 1:
        # Use gunicorn for multiple workers in production
        print("🔧 Starting with Gunicorn (multiple workers)...")
        subprocess.run([
            'gunicorn',
            app_module,
            '--workers', str(workers),
            '--worker-class', 'uvicorn.workers.UvicornWorker',
            '--bind', f'{host}:{port}',
            '--access-logfile', '-',
            '--error-logfile', '-',
            '--log-level', 'info',
            '--timeout', '120',
            '--keep-alive', '5',
            '--max-requests', '1000',
            '--max-requests-jitter', '50'
        ])
    else:
        # Use uvicorn directly for development
        print("🔧 Starting with Uvicorn (single worker)...")
        uvicorn.run(
            app_module,
            host=host,
            port=port,
            reload=False,  # Don't reload in Docker
            log_level="info",
            access_log=True
        )

def main():
    """Main entrypoint function."""
    print("""
╔══════════════════════════════════════╗
║   Ghost Backend Framework Docker     ║
║          Container Starting...        ║
╚══════════════════════════════════════╝
""")
    
    # Validate environment
    if not validate_environment():
        sys.exit(1)
    
    # Wait for services
    if not wait_for_database():
        sys.exit(1)
    
    if not wait_for_redis():
        print("⚠️  Continuing without Redis...")
    
    # Run migrations
    if not run_migrations():
        print("⚠️  Continuing despite migration issues...")
    
    # Start the application
    try:
        start_application()
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()