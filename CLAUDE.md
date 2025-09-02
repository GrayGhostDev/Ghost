# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ghost Backend Framework - A comprehensive, reusable backend development foundation designed for all projects. Built with FastAPI, SQLAlchemy, and modern Python practices.

## Core Architecture

### Module Structure
- `src/ghost/config.py` - Configuration management with env, YAML, and JSON support
- `src/ghost/database.py` - SQLAlchemy async database layer with pooling
- `src/ghost/auth.py` - JWT authentication with bcrypt and RBAC
- `src/ghost/api.py` - FastAPI integration with middleware and standardized responses
- `src/ghost/logging.py` - Structured logging with Loguru
- `src/ghost/utils.py` - Comprehensive utility functions
- `src/ghost/websocket.py` - WebSocket support for real-time communication
- `src/ghost/email.py` - Email sending with SMTP and provider support
- `src/ghost/tasks.py` - Background task processing and scheduling
- `src/ghost/storage.py` - File upload and storage management
- `src/ghost/models.py` - Base models and repository pattern for database operations

### Configuration Loading Order
1. Environment variables (.env file)
2. YAML configuration (config.yaml)
3. JSON configuration (config.json)
4. Runtime overrides (DATABASE_URL always takes precedence)

## Essential Commands

### Development Setup
```bash
# Initial setup
./bin/setup.sh

# Set up development environment
./bin/dev_setup.sh

# Configure security (macOS Keychain-based)
./tools/security/keychain.sh setup
```

### Running the Backend
```bash
# Start complete backend stack (API + Database + Redis)
./bin/start_backend.sh

# Start just the API server
./bin/run_api.sh

# Stop the backend
./bin/stop_backend.sh

# Stop just the API
./bin/stop_api.sh
```

### Database Management (MacPorts PostgreSQL 16)
```bash
# Install PostgreSQL via MacPorts
make db/install

# Initialize database cluster
make db/init

# Start/stop database
make db/start
make db/stop

# Create database and user
make db/create

# Setup keychain credentials
make env/keychain-setup

# Check database status
make db/status
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src/ghost --cov-report=html

# Run specific test categories
pytest -m "unit"        # Unit tests only
pytest -m "integration" # Integration tests only
pytest -m "not slow"    # Skip slow tests

# Run a single test file
pytest tests/test_framework.py

# Run a specific test
pytest tests/test_framework.py::TestGhostFramework::test_config_loading
```

### Code Quality
```bash
# Format code with Black
black src/

# Sort imports with isort
isort src/

# Lint with flake8
flake8 src/

# Type checking with mypy
mypy src/

# Run all quality checks
black src/ && isort src/ && flake8 src/ && mypy src/
```

### Installation
```bash
# Basic installation
pip install -e .

# Install with all features
pip install -e ".[all]"

# Install specific features
pip install -e ".[web]"      # FastAPI and web features
pip install -e ".[database]"  # Database support
pip install -e ".[auth]"      # Authentication
pip install -e ".[email]"     # Email sending capabilities
pip install -e ".[tasks]"     # Background task processing
pip install -e ".[storage]"   # File storage and uploads
pip install -e ".[dev]"       # Development tools
```

## New Backend Components (Phase 1)

### Email Module (ghost.email)
- SMTP email sending with async support
- Multiple provider support (SMTP, SendGrid, AWS SES planned)
- Template rendering with Jinja2
- Bulk email sending
- Email attachments

### Task Processing (ghost.tasks)
- In-memory task queue with priority support
- Background task workers (sync and async)
- Task scheduling with cron-like syntax
- Automatic retries with exponential backoff
- Task status tracking and results

### File Storage (ghost.storage)
- Local filesystem storage with organized structure
- File type validation and categorization
- Image processing (thumbnails, resizing)
- Cloud storage providers planned (S3, Azure, GCS)
- Secure file upload handling

### Database Models (ghost.models)
- Base models with common mixins (timestamps, soft delete, audit)
- User, Role, Permission models for RBAC
- Repository pattern for database operations
- Support for both sync and async operations
- Session tracking and management

## Key Implementation Patterns

### Async Database Operations
All database operations use async/await pattern with context managers:
```python
async with db_manager.get_session() as session:
    # Database operations here
```

### Configuration Access
Configuration is centralized through the Config class:
```python
from ghost import Config, get_config
config = get_config()  # Singleton pattern
```

### JWT Authentication
Token-based authentication with role-based access control:
- Passwords hashed with bcrypt
- JWT tokens with configurable expiration
- User roles: USER, ADMIN, SUPER_ADMIN

### API Response Standardization
All API responses follow the APIResponse pattern:
- Consistent error handling
- Standardized status codes
- Structured response format

## Environment Variables

Critical environment variables (configured in .env):
- `DATABASE_URL` - PostgreSQL connection string (overrides all other DB config)
- `REDIS_URL` - Redis connection for caching/sessions
- `JWT_SECRET_KEY` - Secret for JWT token signing
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `API_HOST` - API host binding (default: 127.0.0.1 for security)
- `API_PORT` - API server port (default: 8000, production: 8080)

## Security Configuration

### Port Security
- **All services bound to 127.0.0.1** by default (not 0.0.0.0)
- **Production uses reverse proxy** (nginx) for external access
- **Docker ports mapped to localhost only** for security
- See `docs/PORT_SECURITY.md` for comprehensive guide
- Port configuration: `config/port-mapping.yaml`
- Nginx example: `config/nginx-example.conf`

### macOS Keychain Integration
Credentials stored securely in macOS Keychain:
- Database passwords
- API keys
- JWT secrets

Access via: `./scripts/secrets/keychain.sh`

### Production Security
- HTTPS/SSL ready
- CORS configuration per frontend
- Rate limiting via SlowAPI
- Input validation with Pydantic
- SQL injection protection via SQLAlchemy ORM
- No SSH keys in repository (deployment via CI/CD)

## Database Schema Management

### Alembic Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Check current version
alembic current
```

## API Documentation

When the API is running:
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc
- Health check: http://localhost:8080/health

## Project-Specific Notes

### Multi-Frontend Support
Framework auto-detects frontend applications:
- React, Angular, Vue, Flutter support
- Dynamic CORS configuration
- Frontend-specific API prefixes
- WebSocket channels per frontend

### Connection Pooling
Default database pool settings:
- Pool size: 10 connections
- Max overflow: 20 connections
- Pool timeout: 30 seconds
- Pool recycle: 3600 seconds

### Test Coverage
- Current requirement: 10% (set low for initial development)
- Production target: 85%
- Coverage reports in htmlcov/

## Common Development Tasks

### Adding a New API Endpoint
1. Create route in appropriate module or `src/ghost/api.py`
2. Use dependency injection for database/auth
3. Return standardized APIResponse
4. Add corresponding tests

### Adding Database Models
1. Define model in appropriate module
2. Create Alembic migration
3. Apply migration
4. Add model tests

### Debugging Database Issues
1. Check connection: `make db/status`
2. Verify credentials in Keychain
3. Check logs in `logs/` directory
4. Test connection: `psql $DATABASE_URL`

## Directory Organization
- `bin/` - Executable scripts for setup and runtime
- `config/` - Configuration templates and examples
- `src/ghost/` - Core framework source code
- `tools/` - Development and security utilities
- `scripts/` - Database and utility scripts
- `tests/` - Test suite
- `docs/` - Comprehensive documentation
- `examples/` - Usage examples

## Important Files
- `pyproject.toml` - Python package configuration and dependencies
- `Makefile` - Database and environment management commands
- `.env` - Environment variables (create from .env.example)
- `config.yaml` - Application configuration
- `alembic.ini` - Database migration configuration