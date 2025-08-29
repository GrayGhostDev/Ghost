#!/usr/bin/env python3
"""
Ghost Backend Framework - Multi-Frontend Startup Script

Simple startup script that detects frontends and starts the backend with proper configuration.
"""

import os
import sys
import subprocess
import secrets
from pathlib import Path

# This file was moved from the project root to tools/
# All imports referencing start_multi_backend should use tools.start_multi_backend

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def setup_environment():
    """Setup environment variables for the backend using keychain."""
    # Load environment from keychain runtime file
    runtime_env_path = os.path.join(os.path.dirname(__file__), '.env.runtime')
    
    if os.path.exists(runtime_env_path):
        print("✅ Loading credentials from keychain...")
        # Execute the runtime environment script to load variables
        result = subprocess.run(['bash', '-c', f'source {runtime_env_path} && env'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            # Parse environment variables from output
            for line in result.stdout.split('\n'):
                if '=' in line and not line.startswith('_'):
                    key, value = line.split('=', 1)
                    if key in ['JWT_SECRET', 'API_KEY', 'ANTHROPIC_ADMIN_API_KEY', 
                              'OPENAI_API_KEY', 'GITHUB_PAT', 'BRAVE_API_KEY',
                              'SENDGRID_API_KEY', 'SENTRY_DSN', 'DB_PASSWORD']:
                        os.environ[key] = value
                        if key in ['JWT_SECRET', 'API_KEY']:
                            print(f"🔑 {key} loaded from keychain")
        else:
            print("⚠️  Failed to load from keychain, using fallback")
            setup_fallback_environment()
    else:
        print("⚠️  Runtime environment not found. Run: ./tools/scripts/secrets/keychain.sh setup")
        setup_fallback_environment()

def setup_fallback_environment():
    """Fallback environment setup if keychain is not available."""
    print("🔄 Setting up fallback environment variables...")
    
    # Generate secure fallback keys if not set
    if not os.environ.get('JWT_SECRET'):
        # Generate a secure JWT secret
        jwt_secret = secrets.token_urlsafe(64)
        os.environ['JWT_SECRET'] = jwt_secret
        print(f"🔑 Generated secure JWT_SECRET")
    
    if not os.environ.get('API_KEY'):
        # Generate a secure API key
        api_key = secrets.token_urlsafe(32)
        os.environ['API_KEY'] = api_key
        print(f"🔐 Generated secure API_KEY")

def detect_frontends():
    """Detect frontend applications using the detector script."""
    print("🔍 Detecting frontend applications...")
    
    try:
        # Run the frontend detector
        result = subprocess.run([
            sys.executable, 
            "tools/scripts/frontend_detector.py",
            "--generate-env"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Frontend detection completed")
            if result.stdout:
                print(result.stdout)
        else:
            print("⚠️  Frontend detection had issues:")
            if result.stderr:
                print(result.stderr)
    
    except Exception as e:
        print(f"❌ Error running frontend detector: {e}")

def start_api():
    """Start the API server with the example application."""
    print("🚀 Starting Ghost Backend API...")
    
    try:
        # Set environment variables
        setup_environment()
        
        # Run the simple API example
        subprocess.run([
            sys.executable,
            "examples/simple_api.py"
        ])
    
    except KeyboardInterrupt:
        print("\n🛑 API server stopped")
    except Exception as e:
        print(f"❌ Error starting API server: {e}")

def main():
    """Main function to start the multi-frontend backend."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ghost Backend Multi-Frontend Startup')
    parser.add_argument('--detect-only', action='store_true', help='Only detect frontends')
    parser.add_argument('--api-only', action='store_true', help='Only start API server')
    parser.add_argument('--port', type=int, default=8888, help='Port to run on')
    
    args = parser.parse_args()
    
    print("🏁 Ghost Backend Framework - Multi-Frontend Support")
    print("=" * 50)
    
    if not args.api_only:
        detect_frontends()
    
    if not args.detect_only:
        # Set API port
        os.environ['API_PORT'] = str(args.port)
        start_api()

if __name__ == "__main__":
    main()
