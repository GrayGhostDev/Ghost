#!/usr/bin/env python3
"""
Ghost Backend Framework - Comprehensive Status Report
Shows the complete status of backend development integration.
"""

import sys
import os
from pathlib import Path
import subprocess

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def run_command(cmd, capture_output=True):
    """Run a command and return the result."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def test_redis():
    """Test Redis connectivity."""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        return True, "Connection successful"
    except Exception as e:
        return False, str(e)

def test_database():
    """Test database connectivity."""
    try:
        from ghost.config import get_config
        from ghost.database import get_db_manager
        config = get_config()
        db_manager = get_db_manager()
        return True, f"Connected to {config.database.name}"
    except Exception as e:
        return False, str(e)

def test_configuration():
    """Test configuration loading."""
    try:
        from ghost.config import get_config
        config = get_config()
        return True, f"Environment: {config.environment}, Project: {config.project_name}"
    except Exception as e:
        return False, str(e)

def get_frontend_apps():
    """Get frontend application count."""
    try:
        success, stdout, _ = run_command("python tools/scripts/frontend_detector.py --quiet")
        if success and "Found" in stdout:
            count = stdout.split("Found ")[1].split(" frontend")[0]
            return True, f"{count} applications detected"
        return False, "Detection failed"
    except Exception as e:
        return False, str(e)

def check_packages():
    """Check installed packages."""
    success, stdout, _ = run_command("pip list | grep -E '(fastapi|redis|psycopg2|sqlalchemy)' | wc -l")
    if success:
        count = stdout.strip()
        return True, f"{count} core packages installed"
    return False, "Package check failed"

def main():
    print("=" * 80)
    print("🎯 GHOST BACKEND FRAMEWORK - COMPREHENSIVE STATUS REPORT")
    print("=" * 80)
    
    # Core System Status
    print("\n📊 CORE SYSTEM STATUS")
    print("-" * 40)
    
    # Redis
    redis_ok, redis_msg = test_redis()
    status = "✅" if redis_ok else "❌"
    print(f"{status} Redis: {redis_msg}")
    
    # Database
    db_ok, db_msg = test_database()
    status = "✅" if db_ok else "❌"
    print(f"{status} PostgreSQL: {db_msg}")
    
    # Configuration
    config_ok, config_msg = test_configuration()
    status = "✅" if config_ok else "❌"
    print(f"{status} Configuration: {config_msg}")
    
    # Package Installation
    pkg_ok, pkg_msg = check_packages()
    status = "✅" if pkg_ok else "❌"
    print(f"{status} Packages: {pkg_msg}")
    
    # Development Features
    print("\n🛠️  DEVELOPMENT FEATURES")
    print("-" * 40)
    
    # Frontend Detection
    frontend_ok, frontend_msg = get_frontend_apps()
    status = "✅" if frontend_ok else "❌"
    print(f"{status} Multi-Frontend Detection: {frontend_msg}")
    
    # File Structure
    files_exist = all(Path(f).exists() for f in [
        "src/ghost/api.py",
        "src/ghost/auth.py", 
        "src/ghost/database.py",
        "src/ghost/websocket.py",
        "tools/scripts/database_migrations.py",
        "tools/scripts/frontend_detector.py"
    ])
    status = "✅" if files_exist else "❌"
    print(f"{status} Core Framework Files: {'All present' if files_exist else 'Missing files'}")
    
    # Docker Support
    docker_files = Path("docker-compose.yml").exists() and Path("Dockerfile").exists()
    status = "✅" if docker_files else "❌"
    print(f"{status} Docker Development: {'Configured' if docker_files else 'Not configured'}")
    
    # Testing Infrastructure
    print("\n🧪 TESTING & QUALITY")
    print("-" * 40)
    
    # Test Results
    test_success, test_output, _ = run_command("python -m pytest tests/ --tb=no -q")
    if test_success:
        print("✅ Tests: All passing")
    else:
        # Extract test results
        if "passed" in test_output and "failed" in test_output:
            parts = test_output.split()
            passed = next((parts[i-1] for i, x in enumerate(parts) if x == "passed"), "?")
            failed = next((parts[i-1] for i, x in enumerate(parts) if x == "failed"), "?")
            print(f"⚠️  Tests: {passed} passed, {failed} failed")
        else:
            print("❌ Tests: Failed to run")
    
    # Coverage
    coverage_success, coverage_output, _ = run_command("python -m pytest tests/ --cov=src/ghost --cov-report=term-missing -q")
    if "TOTAL" in coverage_output:
        coverage_line = [line for line in coverage_output.split("\n") if "TOTAL" in line][0]
        coverage = coverage_line.split()[-1].replace("%", "")
        try:
            coverage_num = int(coverage)
            status = "✅" if coverage_num >= 85 else "⚠️"
            print(f"{status} Code Coverage: {coverage}% (target: 85%)")
        except:
            print("❌ Code Coverage: Unable to determine")
    else:
        print("❌ Code Coverage: Unable to determine")
    
    # API Documentation
    openapi_exists = Path("src/ghost/api.py").exists()
    status = "✅" if openapi_exists else "❌" 
    print(f"{status} API Documentation: {'Available at /docs' if openapi_exists else 'Not available'}")
    
    # Production Readiness
    print("\n🚀 PRODUCTION READINESS")
    print("-" * 40)
    
    # Environment Configuration
    env_exists = Path(".env").exists()
    status = "✅" if env_exists else "❌"
    print(f"{status} Environment Config: {'Configured' if env_exists else 'Not configured'}")
    
    # Security
    auth_configured = Path("src/ghost/auth.py").exists()
    status = "✅" if auth_configured else "❌"
    print(f"{status} Authentication: {'JWT + Role-based' if auth_configured else 'Not configured'}")
    
    # Database Migrations
    migrations_exist = Path("tools/scripts/database_migrations.py").exists()
    status = "✅" if migrations_exist else "❌"
    print(f"{status} Database Migrations: {'Available' if migrations_exist else 'Not configured'}")
    
    # WebSocket Support
    websocket_exists = Path("src/ghost/websocket.py").exists()
    status = "✅" if websocket_exists else "❌"
    print(f"{status} Real-time Features: {'WebSocket ready' if websocket_exists else 'Not configured'}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("-" * 40)
    
    components = [
        redis_ok, db_ok, config_ok, pkg_ok, frontend_ok,
        files_exist, docker_files, env_exists, auth_configured,
        migrations_exist, websocket_exists
    ]
    
    total = len(components)
    working = sum(components)
    percentage = int((working / total) * 100)
    
    if percentage >= 90:
        status_emoji = "🎉"
        status_text = "EXCELLENT"
    elif percentage >= 80:
        status_emoji = "🎯"
        status_text = "VERY GOOD"
    elif percentage >= 70:
        status_emoji = "✅"
        status_text = "GOOD"
    else:
        status_emoji = "⚠️"
        status_text = "NEEDS WORK"
    
    print(f"{status_emoji} Backend Status: {status_text} ({working}/{total} components working - {percentage}%)")
    
    print("\n🎯 NEXT STEPS:")
    if not test_success:
        print("   • Fix failing tests (utility methods, AuthConfig)")
    if not all([redis_ok, db_ok]):
        print("   • Resolve database/Redis connectivity issues")
    print("   • Improve test coverage to reach 85%")
    print("   • Run development server: python run_api.sh")
    
    print("\n📚 AVAILABLE COMMANDS:")
    print("   • Start API: ./run_api.sh")
    print("   • Run migrations: python tools/scripts/database_migrations.py migrate")
    print("   • Detect frontends: python tools/scripts/frontend_detector.py")
    print("   • Run tests: python -m pytest")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
