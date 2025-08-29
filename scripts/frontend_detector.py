#!/usr/bin/env python3
"""
Ghost Backend Framework - Frontend Detection and Integration System

This module automatically detects frontend applications in the development
environment and configures the backend to work with them.
"""

import os
import json
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
import re


@dataclass
class FrontendApp:
    """Configuration for a detected frontend application."""
    name: str
    type: str  # react, vue, nextjs, angular, svelte, etc.
    path: str
    port: int
    description: str = ""
    cors_origin: str = ""
    api_prefix: str = ""
    auth_required: bool = True
    build_dir: str = ""
    env_file: str = ".env"
    package_json: Optional[Dict] = None
    detected_features: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.detected_features is None:
            self.detected_features = []
        if not self.cors_origin:
            self.cors_origin = f"http://localhost:{self.port}"
        if not self.api_prefix:
            self.api_prefix = f"/{self.name.replace('-', '_')}"


class FrontendDetector:
    """Detects and configures frontend applications for the backend."""
    
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or os.getcwd())
        self.detected_frontends: List[FrontendApp] = []
        self.config_path = self.base_path / "config.multi-frontend.yaml"
        self.port_counter = 3000
        
        # Framework detection patterns
        self.framework_patterns = {
            'react': {
                'files': ['package.json'],
                'dependencies': ['react', '@types/react', 'react-dom'],
                'scripts': ['start', 'build'],
                'build_dirs': ['build', 'dist'],
                'config_files': ['craco.config.js', 'webpack.config.js']
            },
            'nextjs': {
                'files': ['package.json', 'next.config.js'],
                'dependencies': ['next', 'react'],
                'scripts': ['dev', 'build', 'start'],
                'build_dirs': ['.next', 'out'],
                'config_files': ['next.config.js', 'next.config.ts']
            },
            'vue': {
                'files': ['package.json'],
                'dependencies': ['vue', '@vue/cli-service', 'vite'],
                'scripts': ['serve', 'build'],
                'build_dirs': ['dist'],
                'config_files': ['vue.config.js', 'vite.config.js']
            },
            'angular': {
                'files': ['package.json', 'angular.json'],
                'dependencies': ['@angular/core', '@angular/cli'],
                'scripts': ['start', 'build'],
                'build_dirs': ['dist'],
                'config_files': ['angular.json', 'tsconfig.json']
            },
            'svelte': {
                'files': ['package.json'],
                'dependencies': ['svelte', '@sveltejs/kit'],
                'scripts': ['dev', 'build'],
                'build_dirs': ['build', 'dist'],
                'config_files': ['svelte.config.js', 'vite.config.js']
            },
            'flutter': {
                'files': ['pubspec.yaml'],
                'dependencies': [],
                'scripts': [],
                'build_dirs': ['build/web'],
                'config_files': ['pubspec.yaml', 'web/index.html']
            }
        }
    
    def scan_directories(self, scan_dirs: Optional[List[str]] = None) -> None:
        """Scan directories for frontend applications."""
        if scan_dirs is None:
            scan_dirs = [
                str(self.base_path.parent),  # Parent directory
                str(self.base_path.parent.parent),  # Grandparent
                str(self.base_path / "frontends"),  # Local frontends dir
            ]
        
        print("🔍 Scanning for frontend applications...")
        
        for scan_dir in scan_dirs:
            scan_path = Path(scan_dir)
            if scan_path.exists():
                print(f"📁 Scanning: {scan_path}")
                self._scan_directory(scan_path)
        
        print(f"✅ Found {len(self.detected_frontends)} frontend applications")
    
    def _scan_directory(self, directory: Path, max_depth: int = 2) -> None:
        """Recursively scan a directory for frontend applications."""
        # Skip problematic directories
        skip_dirs = {
            '.git', '.svn', '.hg',  # Version control
            'node_modules', '__pycache__', '.venv', 'venv',  # Dependencies/Build
            '.next', '.nuxt', 'build', 'dist',  # Build outputs
            'Library', 'System', 'Applications',  # macOS system dirs
            'Google Drive', 'OneDrive', 'Dropbox',  # Cloud storage
            '.Trash', 'Downloads'  # Other problematic dirs
        }
        
        try:
            for item in directory.iterdir():
                if item.is_dir() and item.name not in skip_dirs and not item.name.startswith('.'):
                    # Check if this directory contains a frontend app
                    frontend = self._detect_frontend_type(item)
                    if frontend:
                        self.detected_frontends.append(frontend)
                        print(f"  ✅ Detected {frontend.type}: {frontend.name}")
                    elif max_depth > 0 and not self._looks_like_dependency_dir(item):
                        # Continue scanning subdirectories
                        self._scan_directory(item, max_depth - 1)
        except (PermissionError, OSError, TimeoutError):
            pass
    
    def _looks_like_dependency_dir(self, directory: Path) -> bool:
        """Check if a directory looks like it contains dependencies/build artifacts."""
        name = directory.name.lower()
        dependency_indicators = [
            'node_modules', '__pycache__', 'build', 'dist', '.next',
            'coverage', '.coverage', 'htmlcov', 'target', 'bin',
            '.gradle', '.maven', 'vendor', 'bower_components'
        ]
        return any(indicator in name for indicator in dependency_indicators)
    
    def _detect_frontend_type(self, directory: Path) -> Optional[FrontendApp]:
        """Detect the type of frontend application in a directory."""
        try:
            package_json_path = directory / "package.json"
            
            # Check for package.json first (with timeout protection)
            if self._safe_path_exists(package_json_path):
                try:
                    with open(package_json_path) as f:
                        package_data = json.load(f)
                    
                    dependencies = {
                        **package_data.get('dependencies', {}),
                        **package_data.get('devDependencies', {})
                    }
                    
                    # Detect framework type
                    framework_type = self._identify_framework(directory, dependencies)
                    if framework_type:
                        return self._create_frontend_app(
                            directory, framework_type, package_data
                        )
                except (json.JSONDecodeError, Exception) as e:
                    print(f"  ⚠️  Error reading package.json in {directory}: {e}")
            
            # Check for Flutter (with timeout protection)
            pubspec_path = directory / "pubspec.yaml"
            if self._safe_path_exists(pubspec_path):
                try:
                    with open(pubspec_path) as f:
                        pubspec_data = yaml.safe_load(f)
                    
                    if 'flutter' in pubspec_data.get('dependencies', {}):
                        return self._create_flutter_app(directory, pubspec_data)
                except Exception as e:
                    print(f"  ⚠️  Error reading pubspec.yaml in {directory}: {e}")
        
        except (OSError, TimeoutError, PermissionError):
            pass
        
        return None
    
    def _safe_path_exists(self, path: Path) -> bool:
        """Safely check if a path exists with timeout protection."""
        try:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Path check timeout")
            
            # Set a 2-second timeout for file operations
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(2)
            
            try:
                result = path.exists()
                signal.alarm(0)  # Cancel the alarm
                return result
            except TimeoutError:
                return False
            
        except (OSError, PermissionError, AttributeError):
            # AttributeError for systems without signal.SIGALRM (Windows)
            try:
                return path.exists()
            except:
                return False
    
    def _identify_framework(self, directory: Path, dependencies: Dict[str, str]) -> Optional[str]:
        """Identify the framework type based on dependencies and files."""
        scores = {}
        
        for framework, patterns in self.framework_patterns.items():
            score = 0
            
            # Check dependencies
            for dep in patterns['dependencies']:
                if dep in dependencies:
                    score += 2
            
            # Check for config files
            for config_file in patterns['config_files']:
                if (directory / config_file).exists():
                    score += 1
            
            if score > 0:
                scores[framework] = score
        
        # Return the framework with the highest score
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        return None
    
    def _create_frontend_app(self, directory: Path, framework_type: str, package_data: Dict) -> FrontendApp:
        """Create a FrontendApp instance from detected information."""
        name = package_data.get('name', directory.name)
        description = package_data.get('description', f"{framework_type.title()} application")
        
        # Detect build directory
        patterns = self.framework_patterns[framework_type]
        build_dir = 'build'  # default
        for build_dir_option in patterns['build_dirs']:
            if (directory / build_dir_option).exists():
                build_dir = build_dir_option
                break
        
        # Detect features
        features = self._detect_features(directory, package_data)
        
        # Assign port
        port = self._get_next_port()
        
        return FrontendApp(
            name=name,
            type=framework_type,
            path=str(directory),
            port=port,
            description=description,
            build_dir=build_dir,
            package_json=package_data,
            detected_features=features
        )
    
    def _create_flutter_app(self, directory: Path, pubspec_data: Dict) -> FrontendApp:
        """Create a FrontendApp instance for Flutter applications."""
        name = pubspec_data.get('name', directory.name)
        description = pubspec_data.get('description', 'Flutter application')
        
        port = self._get_next_port()
        
        return FrontendApp(
            name=name,
            type='flutter',
            path=str(directory),
            port=port,
            description=description,
            build_dir='build/web',
            detected_features=['mobile', 'web']
        )
    
    def _detect_features(self, directory: Path, package_data: Dict) -> List[str]:
        """Detect features and capabilities of the frontend application."""
        features = []
        dependencies = {
            **package_data.get('dependencies', {}),
            **package_data.get('devDependencies', {})
        }
        
        # Authentication features
        auth_deps = ['@auth0/auth0-react', 'firebase', 'supabase', 'next-auth']
        if any(dep in dependencies for dep in auth_deps):
            features.append('authentication')
        
        # State management
        state_deps = ['redux', '@reduxjs/toolkit', 'zustand', 'mobx', 'vuex', 'pinia']
        if any(dep in dependencies for dep in state_deps):
            features.append('state_management')
        
        # UI frameworks
        ui_deps = ['antd', '@mui/material', 'react-bootstrap', 'chakra-ui', 'vuetify']
        if any(dep in dependencies for dep in ui_deps):
            features.append('ui_framework')
        
        # PWA features
        pwa_deps = ['workbox-webpack-plugin', '@vue/cli-plugin-pwa', 'next-pwa']
        if any(dep in dependencies for dep in pwa_deps):
            features.append('pwa')
        
        # Testing
        test_deps = ['jest', 'cypress', '@testing-library/react', 'vitest']
        if any(dep in dependencies for dep in test_deps):
            features.append('testing')
        
        # Mobile
        mobile_deps = ['react-native', '@ionic/react', '@ionic/vue', 'capacitor']
        if any(dep in dependencies for dep in mobile_deps):
            features.append('mobile')
        
        return features
    
    def _get_next_port(self) -> int:
        """Get the next available port for a frontend application."""
        port = self.port_counter
        self.port_counter += 1
        return port
    
    def generate_backend_config(self) -> Dict[str, Any]:
        """Generate backend configuration for detected frontends."""
        config = {
            'backend': {
                'name': 'Ghost Backend Framework',
                'version': '1.0.0',
                'api': {
                    'host': '0.0.0.0',
                    'port': 8888,
                    'base_path': '/api/v1'
                }
            },
            'frontends': {},
            'cors': {
                'allow_credentials': True,
                'allowed_origins': []
            },
            'routing': {
                'prefixes': {}
            }
        }
        
        # Group frontends by type
        for frontend in self.detected_frontends:
            if frontend.type not in config['frontends']:
                config['frontends'][frontend.type] = []
            
            frontend_config = {
                'name': frontend.name,
                'description': frontend.description,
                'port': frontend.port,
                'path': frontend.path,
                'build_dir': frontend.build_dir,
                'cors_origin': frontend.cors_origin,
                'api_prefix': frontend.api_prefix,
                'auth_required': frontend.auth_required,
                'detected_features': frontend.detected_features
            }
            
            config['frontends'][frontend.type].append(frontend_config)
            config['cors']['allowed_origins'].append(frontend.cors_origin)
            config['routing']['prefixes'][frontend.name.replace('-', '_')] = frontend.api_prefix
        
        return config
    
    def save_config(self, config_path: Optional[str] = None) -> None:
        """Save the generated configuration to a YAML file."""
        if config_path is None:
            config_path = str(self.config_path)
        
        config = self.generate_backend_config()
        
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
        
        print(f"💾 Configuration saved to: {config_path}")
    
    def generate_env_files(self) -> None:
        """Generate environment files for detected frontends."""
        print("📝 Generating environment files for frontends...")
        
        for frontend in self.detected_frontends:
            env_content = self._generate_env_content(frontend)
            env_path = Path(frontend.path) / frontend.env_file
            
            try:
                with open(env_path, 'w') as f:
                    f.write(env_content)
                print(f"  ✅ {frontend.name}: {env_path}")
            except Exception as e:
                print(f"  ❌ {frontend.name}: Error writing {env_path} - {e}")
    
    def _generate_env_content(self, frontend: FrontendApp) -> str:
        """Generate environment file content for a frontend."""
        content = [
            f"# Environment configuration for {frontend.name}",
            f"# Generated by Ghost Backend Framework",
            "",
            f"# Backend API configuration",
            f"REACT_APP_API_URL=http://localhost:8888{frontend.api_prefix}",
            f"VITE_API_URL=http://localhost:8888{frontend.api_prefix}",
            f"NEXT_PUBLIC_API_URL=http://localhost:8888{frontend.api_prefix}",
            "",
            f"# WebSocket configuration",
            f"REACT_APP_WS_URL=ws://localhost:8889/ws",
            f"VITE_WS_URL=ws://localhost:8889/ws",
            f"NEXT_PUBLIC_WS_URL=ws://localhost:8889/ws",
            "",
            f"# Development configuration",
            f"NODE_ENV=development",
            f"PORT={frontend.port}",
            "",
            f"# Feature flags",
        ]
        
        for feature in frontend.detected_features or []:
            content.append(f"REACT_APP_FEATURE_{feature.upper()}=true")
            content.append(f"VITE_FEATURE_{feature.upper()}=true")
            content.append(f"NEXT_PUBLIC_FEATURE_{feature.upper()}=true")
        
        return '\n'.join(content)
    
    def print_summary(self) -> None:
        """Print a summary of detected frontends."""
        print("\n📊 Frontend Detection Summary")
        print("=" * 50)
        
        if not self.detected_frontends:
            print("No frontend applications detected.")
            return
        
        for frontend in self.detected_frontends:
            print(f"\n🌐 {frontend.name}")
            print(f"   Type: {frontend.type}")
            print(f"   Port: {frontend.port}")
            print(f"   Path: {frontend.path}")
            print(f"   Features: {', '.join(frontend.detected_features or [])}")
            print(f"   API Prefix: {frontend.api_prefix}")
            print(f"   CORS Origin: {frontend.cors_origin}")


def main():
    """Main function to run frontend detection."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Detect and configure frontend applications')
    parser.add_argument('--scan-dirs', nargs='*', help='Directories to scan')
    parser.add_argument('--config-file', help='Configuration file to generate')
    parser.add_argument('--generate-env', action='store_true', help='Generate .env files')
    
    args = parser.parse_args()
    
    detector = FrontendDetector()
    detector.scan_directories(args.scan_dirs)
    detector.print_summary()
    
    if detector.detected_frontends:
        config_file = args.config_file or "config.detected-frontends.yaml"
        detector.save_config(config_file)
        
        if args.generate_env:
            detector.generate_env_files()
    
    print("\n✅ Frontend detection complete!")


if __name__ == "__main__":
    main()
