# Ghost Backend Framework - Directory Structure

This document outlines the organized directory structure of the Ghost Backend Framework.

## 📁 Root Directory Structure

```
Ghost/
├── 📁 bin/                     # Executable scripts
├── 📁 config/                  # Configuration files
├── 📁 docs/                    # Documentation
├── 📁 src/                     # Source code
├── 📁 tests/                   # Test files
├── 📁 scripts/                 # Utility scripts
├── 📁 tools/                   # Development and maintenance tools
├── 📁 logs/                    # Log files
├── 📁 uploads/                 # File uploads
├── 📁 backups/                 # Backup files
├── 📁 migrations/              # Database migrations
└── 📁 examples/                # Example implementations
```

## 📂 Directory Details

### `/bin/` - Executable Scripts
Main operational scripts for the backend:
- `start_backend.sh` - Complete backend startup workflow
- `stop_backend.sh` - Complete backend shutdown
- `run_api.sh` - Basic API startup
- `run_api_8001.sh` - API on alternate port
- `stop_api.sh` - API shutdown
- `setup.sh` - Initial setup script
- `dev_setup.sh` - Development environment setup
- `make-safe.sh` - Security hardening script

### `/config/` - Configuration Files
System configuration and environment templates:
- `config.detected-frontends.yaml`
- `config.multi-frontend.yaml`
- `config.production.yaml`
- `environments/` - Environment-specific configs
  - `.env.example` - Example environment variables
  - `.env.production.example` - Production environment template
  - `.env.docker.template` - Docker environment template

### `/src/` - Source Code
Main application source code:
- `ghost/` - Core Ghost backend framework
  - `api.py` - API endpoints and routing
  - `auth.py` - Authentication and authorization
  - `config.py` - Configuration management
  - `database.py` - Database connections and models
  - `logging.py` - Logging configuration
  - `utils.py` - Utility functions
  - `websocket.py` - WebSocket handling

### `/tools/` - Development Tools
Development and maintenance utilities:
- `setup/` - Setup and installation tools
  - `env_helpers.sh` - Environment helper functions
  - `install_macports.sh` - MacPorts installation
  - `migrate_old.sh` - Migration utilities
- `security/` - Security management tools
  - `keychain.sh` - Keychain credential management
  - `dotenv_sync.sh` - Environment synchronization
  - `runtime_env.sh` - Runtime environment setup
- `backend_manager.py` - Backend management utilities
- `start_multi_backend.py` - Multi-backend orchestration

### `/scripts/` - Utility Scripts
Database and system utility scripts:
- `database_migrations.py` - Database migration runner
- `complete_setup.py` - Complete system setup
- `backend_status.py` - Backend status checking
- `frontend_detector.py` - Frontend detection utilities
- `frontend_watcher.py` - Frontend file watching
- `verify_security.sh` - Security verification

### `/docs/` - Documentation
Project documentation:
- `DATABASE_SETUP.md` - Database setup guide
- `DEPLOYMENT_GUIDE.md` - Deployment instructions
- `SECURITY_GUIDE.md` - Security implementation guide
- `PROXYMAN_FIX.md` - Proxy configuration fixes

### `/tests/` - Test Suite
Testing framework and test cases:
- `test_framework.py` - Main test framework
- Unit tests and integration tests

## 🚀 Quick Start Commands

From project root:
```bash
# Start the complete backend
./bin/start_backend.sh

# Stop the complete backend
./bin/stop_backend.sh

# Run just the API
./bin/run_api.sh

# Stop the API
./bin/stop_api.sh
```

## 🔧 Development Workflow

1. **Initial Setup**: `./bin/setup.sh`
2. **Development Setup**: `./bin/dev_setup.sh`
3. **Security Setup**: `./tools/security/keychain.sh setup`
4. **Start Development**: `./bin/start_backend.sh`

## 📋 Configuration Management

- Production configs: `config/config.production.yaml`
- Environment templates: `config/environments/`
- Runtime environment: `.env.runtime` (auto-generated)
- Secure credentials: macOS Keychain (managed by `tools/security/keychain.sh`)

## 🔐 Security

All sensitive credentials are managed through macOS Keychain Services using the tools in `tools/security/`. Never commit `.env.runtime` or files containing actual credentials.
