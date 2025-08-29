#!/usr/bin/env python3
"""
Ghost Backend Framework - Frontend Watcher and Auto-Configuration

This module watches for new frontend applications and automatically
configures the backend to work with them.
"""

import os
import time
import yaml
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import List, Dict, Any, Optional
import asyncio
import subprocess
import threading
from frontend_detector import FrontendDetector


class FrontendWatcher(FileSystemEventHandler):
    """Watches for new frontend applications and auto-configures them."""
    
    def __init__(self, backend_path: str, watch_dirs: Optional[List[str]] = None):
        self.backend_path = Path(backend_path)
        self.watch_dirs = watch_dirs or [
            str(self.backend_path.parent),
            str(self.backend_path.parent.parent)
        ]
        self.detector = FrontendDetector(str(self.backend_path))
        self.last_scan = 0
        self.scan_cooldown = 5  # seconds
        
        # Load current configuration
        self.current_config = self._load_current_config()
        
        print(f"🔍 Frontend Watcher initialized")
        print(f"📁 Backend path: {self.backend_path}")
        print(f"👀 Watching directories: {self.watch_dirs}")
    
    def _load_current_config(self) -> Dict[str, Any]:
        """Load the current frontend configuration."""
        config_path = self.backend_path / "config.detected-frontends.yaml"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"⚠️  Error loading config: {e}")
        return {}
    
    def on_created(self, event):
        """Handle file/directory creation events."""
        if event.is_directory:
            self._check_for_frontend(str(event.src_path))
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory:
            # Check if a package.json or similar was modified
            filename = os.path.basename(event.src_path)
            if filename in ['package.json', 'pubspec.yaml', 'angular.json']:
                self._trigger_rescan()
    
    def _check_for_frontend(self, directory_path: str):
        """Check if a new directory contains a frontend application."""
        current_time = time.time()
        if current_time - self.last_scan < self.scan_cooldown:
            return
        
        directory = Path(directory_path)
        print(f"🔍 Checking new directory: {directory}")
        
        # Check if this directory contains frontend files
        frontend_indicators = [
            'package.json', 'pubspec.yaml', 'angular.json',
            'next.config.js', 'vue.config.js', 'svelte.config.js'
        ]
        
        if any((directory / indicator).exists() for indicator in frontend_indicators):
            print(f"✨ Potential frontend detected: {directory.name}")
            self._trigger_rescan()
    
    def _trigger_rescan(self):
        """Trigger a full rescan of frontend applications."""
        current_time = time.time()
        if current_time - self.last_scan < self.scan_cooldown:
            return
        
        self.last_scan = current_time
        
        print("🔄 Triggering frontend rescan...")
        threading.Thread(target=self._perform_rescan, daemon=True).start()
    
    def _perform_rescan(self):
        """Perform the actual rescan and reconfiguration."""
        try:
            time.sleep(1)  # Brief delay to ensure files are fully written
            
            # Detect frontends
            old_frontends = set()
            if 'frontends' in self.current_config:
                for frontend_type, apps in self.current_config['frontends'].items():
                    for app in apps:
                        old_frontends.add(app['name'])
            
            # Scan for new frontends
            self.detector.detected_frontends = []
            self.detector.scan_directories(self.watch_dirs)
            
            new_frontends = set(f.name for f in self.detector.detected_frontends)
            
            # Check for changes
            added_frontends = new_frontends - old_frontends
            removed_frontends = old_frontends - new_frontends
            
            if added_frontends or removed_frontends:
                print(f"📊 Frontend changes detected:")
                if added_frontends:
                    print(f"  ➕ Added: {', '.join(added_frontends)}")
                if removed_frontends:
                    print(f"  ➖ Removed: {', '.join(removed_frontends)}")
                
                # Save new configuration
                self.detector.save_config()
                self.detector.generate_env_files()
                self.current_config = self._load_current_config()
                
                # Trigger backend restart if needed
                self._trigger_backend_restart()
                
                # Send notifications
                self._send_notifications(added_frontends, removed_frontends)
            
        except Exception as e:
            print(f"❌ Error during rescan: {e}")
    
    def _trigger_backend_restart(self):
        """Trigger a backend restart to apply new configuration."""
        print("🔄 Triggering backend restart...")
        
        # Create a restart signal file
        restart_file = self.backend_path / ".restart"
        restart_file.touch()
        
        # Try to restart the backend if running via pm2 or similar
        try:
            subprocess.run(["pm2", "restart", "ghost-backend"], 
                         capture_output=True, check=False)
        except FileNotFoundError:
            pass
        
        # Try to restart via systemctl if it's a service
        try:
            subprocess.run(["systemctl", "--user", "restart", "ghost-backend"], 
                         capture_output=True, check=False)
        except FileNotFoundError:
            pass
    
    def _send_notifications(self, added: set, removed: set):
        """Send notifications about frontend changes."""
        # Create notification file
        notifications = {
            'timestamp': time.time(),
            'added_frontends': list(added),
            'removed_frontends': list(removed),
            'total_frontends': len(self.detector.detected_frontends)
        }
        
        notification_file = self.backend_path / "frontend-changes.json"
        import json
        with open(notification_file, 'w') as f:
            json.dump(notifications, f, indent=2)
        
        print(f"📢 Notification saved to: {notification_file}")


def start_watcher(backend_path: str, watch_dirs: Optional[List[str]] = None):
    """Start the frontend watcher."""
    event_handler = FrontendWatcher(backend_path, watch_dirs)
    observer = Observer()
    
    # Add watchers for each directory
    for watch_dir in event_handler.watch_dirs:
        if Path(watch_dir).exists():
            observer.schedule(event_handler, watch_dir, recursive=True)
            print(f"👁️  Watching: {watch_dir}")
    
    observer.start()
    print("🚀 Frontend watcher started!")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("🛑 Frontend watcher stopped")
    
    observer.join()


def main():
    """Main function to start the frontend watcher."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Watch for new frontend applications')
    parser.add_argument('--backend-path', default='.', help='Path to backend directory')
    parser.add_argument('--watch-dirs', nargs='*', help='Directories to watch')
    
    args = parser.parse_args()
    
    start_watcher(args.backend_path, args.watch_dirs)


if __name__ == "__main__":
    main()
