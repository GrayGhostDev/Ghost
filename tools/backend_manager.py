#!/usr/bin/env python3
"""
Ghost Backend Framework - Multi-Frontend Backend Manager

This is the main entry point for running the backend with multi-frontend support.
It integrates frontend detection, configuration, and API serving.
"""

import os
import sys
import yaml
import asyncio
import uvicorn
from pathlib import Path
from typing import Dict, List, Any, Optional
import threading
import time
import signal

# This file was moved from the project root to tools/
# All imports referencing backend_manager should use tools.backend_manager

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ghost import setup_logging, get_logger, get_config
from ghost.api import get_api_manager
from scripts.frontend_detector import FrontendDetector
from scripts.frontend_watcher import start_watcher


class MultiBackendManager:
    """Manages the backend with multi-frontend support."""
    
    def __init__(self, config_file: str = "config.production.yaml"):
        self.base_path = Path(__file__).parent.parent
        self.config_file = config_file
        self.logger = get_logger("backend_manager")
        
        # Initialize components
        self.detector = FrontendDetector(str(self.base_path))
        self.api_manager = None
        self.watcher_thread = None
        self.server = None
        
        # Configuration
        self.config = self._load_config()
        self.frontend_config = {}
        
        # Setup logging
        setup_logging()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load the main configuration file."""
        config_path = self.base_path / self.config_file
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {}
    
    def detect_frontends(self, scan_dirs: Optional[List[str]] = None) -> None:
        """Detect frontend applications and generate configuration."""
        self.logger.info("🔍 Detecting frontend applications...")
        
        # Scan for frontends
        self.detector.scan_directories(scan_dirs)
        self.detector.print_summary()
        
        if self.detector.detected_frontends:
            # Generate configuration
            config_file = "config.detected-frontends.yaml"
            self.detector.save_config(config_file)
            self.detector.generate_env_files()
            
            # Load the generated configuration
            self.frontend_config = self.detector.generate_backend_config()
            
            self.logger.info(f"✅ Configured {len(self.detector.detected_frontends)} frontend applications")
        else:
            self.logger.info("ℹ️  No frontend applications detected")
    
    def setup_cors(self) -> List[str]:
        """Setup CORS origins based on detected frontends."""
        origins = [
            "http://localhost:3000",  # Default React
            "http://localhost:8080",  # Default Vue
            "http://localhost:4200",  # Default Angular
        ]
        
        # Add detected frontend origins
        if 'cors' in self.frontend_config and 'allowed_origins' in self.frontend_config['cors']:
            origins.extend(self.frontend_config['cors']['allowed_origins'])
        
        # Add from main config
        if 'api' in self.config and 'cors' in self.config['api']:
            config_origins = self.config['api']['cors'].get('origins', [])
            origins.extend(config_origins)
        
        # Remove duplicates and return
        return list(set(origins))
    
    def create_api_routes(self) -> Dict[str, str]:
        """Create API route mappings for different frontends."""
        routes = {
            'shared': '/api/v1',
            'admin': '/api/v1/admin',
            'user': '/api/v1/user',
        }
        
        # Add routes from frontend configuration
        if 'routing' in self.frontend_config and 'prefixes' in self.frontend_config['routing']:
            routes.update(self.frontend_config['routing']['prefixes'])
        
        return routes
    
    def start_watcher(self) -> None:
        """Start the frontend watcher in a separate thread."""
        def run_watcher():
            try:
                from scripts.frontend_watcher import start_watcher
                watch_dirs = [
                    str(self.base_path.parent),
                    str(self.base_path.parent.parent),
                ]
                start_watcher(str(self.base_path), watch_dirs)
            except Exception as e:
                self.logger.error(f"Error in frontend watcher: {e}")
        
        self.watcher_thread = threading.Thread(target=run_watcher, daemon=True)
        self.watcher_thread.start()
        self.logger.info("👁️  Frontend watcher started")
    
    def create_fastapi_app(self):
        """Create and configure the FastAPI application."""
        # Set up environment variables
        os.environ.setdefault('JWT_SECRET', self.config.get('api', {}).get('jwt_secret', ''))
        os.environ.setdefault('API_KEY', self.config.get('api', {}).get('api_key', ''))
        
        # Get the API manager
        self.api_manager = get_api_manager()
        app = self.api_manager.app
        
        # Update CORS origins
        cors_origins = self.setup_cors()
        self.logger.info(f"🌐 CORS origins: {cors_origins}")
        
        # Update app middleware (if needed)
        # This would require modifying the ghost.api module to support dynamic CORS
        
        # Add frontend-specific routes
        self._add_frontend_routes(app)
        
        return app
    
    def _add_frontend_routes(self, app) -> None:
        """Add frontend-specific routes and endpoints."""
        from fastapi import APIRouter
        from fastapi.responses import JSONResponse
        
        # Frontend info endpoint
        @app.get("/api/v1/frontend/config")
        async def get_frontend_config():
            return JSONResponse({
                "frontends": self.frontend_config.get('frontends', {}),
                "detected_count": len(self.detector.detected_frontends),
                "cors_origins": self.setup_cors(),
                "api_routes": self.create_api_routes()
            })
        
        # Health check with frontend info
        @app.get("/api/v1/health/full")
        async def health_check_full():
            return JSONResponse({
                "status": "healthy",
                "backend": {
                    "name": "Ghost Backend Framework",
                    "version": "1.0.0"
                },
                "frontends": {
                    "detected": len(self.detector.detected_frontends),
                    "applications": [
                        {
                            "name": fe.name,
                            "type": fe.type,
                            "port": fe.port,
                            "features": fe.detected_features or []
                        }
                        for fe in self.detector.detected_frontends
                    ]
                },
                "database": {
                    "connected": True,  # TODO: Add actual DB health check
                    "name": self.config.get('database', {}).get('name', 'ghost')
                }
            })
    
    def run_server(self, host: str = "0.0.0.0", port: int = 8888, reload: bool = False) -> None:
        """Run the FastAPI server."""
        app = self.create_fastapi_app()
        if app is None:
            raise RuntimeError("FastAPI app instance is None. Cannot start server.")
        
        self.logger.info(f"🚀 Starting Ghost Backend Framework on {host}:{port}")
        self.logger.info(f"📚 API Documentation: http://{host}:{port}/docs")
        
        # Configure uvicorn
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            reload=reload,
            log_level="info",
            access_log=True
        )
        
        self.server = uvicorn.Server(config)
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            self.logger.info("🛑 Shutting down server...")
            if self.server is not None:
                self.server.should_exit = True        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run the server
        self.server.run()
    
    def run(self, 
            host: str = "0.0.0.0", 
            port: int = 8888, 
            reload: bool = False,
            enable_watcher: bool = True,
            scan_dirs: Optional[List[str]] = None) -> None:
        """Run the complete multi-frontend backend system."""
        
        self.logger.info("🏁 Starting Ghost Backend Framework with Multi-Frontend Support")
        
        # Step 1: Detect frontends
        self.detect_frontends(scan_dirs)
        
        # Step 2: Start frontend watcher (if enabled)
        if enable_watcher:
            self.start_watcher()
        
        # Step 3: Run the API server
        self.run_server(host, port, reload)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Ghost Backend Framework - Multi-Frontend Support'
    )
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8888, help='Port to bind to')
    parser.add_argument('--config', default='config.production.yaml', help='Configuration file')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    parser.add_argument('--no-watcher', action='store_true', help='Disable frontend watcher')
    parser.add_argument('--scan-dirs', nargs='*', help='Directories to scan for frontends')
    parser.add_argument('--detect-only', action='store_true', help='Only detect frontends, don\'t start server')
    
    args = parser.parse_args()
    
    manager = MultiBackendManager(args.config)
    
    if args.detect_only:
        manager.detect_frontends(args.scan_dirs)
        return
    
    try:
        manager.run(
            host=args.host,
            port=args.port,
            reload=args.reload,
            enable_watcher=not args.no_watcher,
            scan_dirs=args.scan_dirs
        )
    except KeyboardInterrupt:
        print("\n👋 Backend shutdown complete")
    except Exception as e:
        print(f"❌ Error starting backend: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
