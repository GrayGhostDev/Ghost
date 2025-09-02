#!/usr/bin/env python3
"""
Docker Entrypoint for Ghost Backend Framework

This script handles container startup without relying on macOS keychain.
Environment variables should be provided via docker-compose or Docker secrets.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, '/app/src')

def wait_for_database(max_retries=30, retry_interval=2):
    """Wait for PostgreSQL to be ready."""
    db_host = os.environ.get('DB_HOST', 'postgres')
    db_port = os.environ.get('DB_PORT', '5432')
    db_name = os.environ.get('DB_NAME', 'ghost')
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
                print(f"✅ PostgreSQL is ready!")
                return True
        except subprocess.TimeoutExpired:
            pass
        
        if i < max_retries - 1:
            print(f"  Attempt {i+1}/{max_retries} failed, retrying in {retry_interval}s...")
            time.sleep(retry_interval)
    
    print(f"❌ PostgreSQL not available after {max_retries} attempts")
    return False

def wait_for_redis(max_retries=30, retry_interval=2):
    """Wait for Redis to be ready."""
    redis_host = os.environ.get('REDIS_HOST', 'redis')
    redis_port = os.environ.get('REDIS_PORT', '6379')
    
    print(f"🔄 Waiting for Redis at {redis_host}:{redis_port}...")
    
    # Import here to avoid issues if redis isn't installed
    try:
        import redis
        r = redis.Redis(host=redis_host, port=int(redis_port), socket_connect_timeout=5)
        
        for i in range(max_retries):
            try:
                if r.ping():
                    print(f"✅ Redis is ready!")
                    return True
            except (redis.ConnectionError, redis.TimeoutError):
                pass
            
            if i < max_retries - 1:
                print(f"  Attempt {i+1}/{max_retries} failed, retrying in {retry_interval}s...")
                time.sleep(retry_interval)
    except ImportError:
        print("⚠️  Redis client not installed, skipping Redis check")
        return True
    
    print(f"❌ Redis not available after {max_retries} attempts")
    return False

def run_migrations():
    """Run database migrations if alembic is configured."""
    alembic_ini = Path('/app/alembic.ini')
    if alembic_ini.exists():
        print("🔄 Running database migrations...")
        try:
            # Temporarily skip migrations until models are properly set up
            print("⚠️  Migrations temporarily disabled for initial setup")
            return True
            
            # Original migration code (will be re-enabled later)
            # result = subprocess.run(
            #     ['alembic', 'upgrade', 'head'],
            #     capture_output=True,
            #     text=True,
            #     cwd='/app'
            # )
            # if result.returncode == 0:
            #     print("✅ Migrations completed successfully")
            #     return True
            # else:
            #     print(f"⚠️  Migration failed: {result.stderr}")
            #     return False
        except FileNotFoundError:
            print("⚠️  Alembic not installed, skipping migrations")
            return True
    else:
        print("ℹ️  No alembic.ini found, skipping migrations")
        return True

def validate_environment():
    """Validate required environment variables."""
    required_vars = []
    recommended_vars = ['JWT_SECRET', 'API_KEY', 'DB_PASSWORD']
    
    missing_required = [var for var in required_vars if not os.environ.get(var)]
    missing_recommended = [var for var in recommended_vars if not os.environ.get(var)]
    
    if missing_required:
        print(f"❌ Missing required environment variables: {', '.join(missing_required)}")
        return False
    
    if missing_recommended:
        print(f"⚠️  Missing recommended environment variables: {', '.join(missing_recommended)}")
        print("   Using default values - NOT suitable for production!")
    
    return True

def start_application():
    """Start the FastAPI application."""
    import uvicorn
    from ghost import get_config
    
    config = get_config()
    
    # Determine the application module
    app_module = os.environ.get('APP_MODULE', 'examples.simple_api:app')
    
    # Get host and port from environment or config
    host = os.environ.get('API_HOST', '0.0.0.0')  # 0.0.0.0 is OK inside container
    port = int(os.environ.get('API_PORT', '8888'))
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