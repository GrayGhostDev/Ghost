# Ghost Backend Framework

A comprehensive, reusable backend development foundation designed to be used across all your development projects. This framework provides common patterns, utilities, and configurations that eliminate repetitive setup work and ensure consistency across your applications.

## 🚀 Features

### Core Foundation
- **Configuration Management**: Environment-based configuration with YAML, JSON, and .env support
- **Advanced Logging**: Structured logging with Loguru, file rotation, and multiple output formats
- **Comprehensive Utilities**: Date/time, string manipulation, validation, serialization, and more

### Optional Components
- **Database Layer**: SQLAlchemy 2.0 with async support for PostgreSQL, SQLite, Redis, and MongoDB
- **Authentication**: JWT-based auth with bcrypt hashing and role-based access control (RBAC)
- **API Framework**: FastAPI integration with middleware, rate limiting, and standardized responses

## 📦 Quick Start

### 1. Initial Setup
```bash
# Clone and enter the project
cd Ghost

# Run initial setup
./bin/setup.sh

# Set up development environment
./bin/dev_setup.sh

# Configure security (keychain-based credentials)
./tools/security/keychain.sh setup
```

### 2. Start the Backend
```bash
# Start complete backend stack
./bin/start_backend.sh

# Or start just the API
./bin/run_api.sh
```

### 3. Stop the Backend
```bash
# Stop complete backend stack
./bin/stop_backend.sh

# Or stop just the API
./bin/stop_api.sh
```

## 📁 Project Structure

```
Ghost/
├── bin/           # Executable scripts (start/stop/setup)
├── config/        # Configuration files and templates
├── src/ghost/     # Core framework source code
├── tools/         # Development and security tools
├── scripts/       # Database and utility scripts  
├── tests/         # Test suite
├── docs/          # Documentation
└── examples/      # Usage examples
```

See [docs/DIRECTORY_STRUCTURE.md](docs/DIRECTORY_STRUCTURE.md) for detailed organization and all documentation files.

## 📦 Installation

### Basic Installation
```bash
pip install -e .
```

### With All Features
```bash
pip install -e ".[all]"
```

### Selective Installation
```bash
# Web API features
pip install -e ".[web]"

# Database features  
pip install -e ".[database]"

# Authentication features
pip install -e ".[auth]"

# Development tools
pip install -e ".[dev]"
```

## 🏗️ Quick Start

### 1. Basic Configuration
```python
from ghost import Config, setup_logging, get_logger

# Initialize configuration (loads from .env, config.yaml, etc.)
config = Config()
setup_logging(config.logging)
logger = get_logger(__name__)

logger.info("Ghost Backend Framework initialized!")
```

### 2. Database Integration
```python
from ghost import DatabaseManager, get_db_manager

# Initialize database
db_manager = DatabaseManager(config.database)
await db_manager.initialize()

# Use database session
async with db_manager.get_session() as session:
    # Your database operations here
    pass
```

### 3. API Development
```python
from ghost import APIManager, get_api_manager
from fastapi import FastAPI

# Create FastAPI app with Ghost enhancements
api_manager = APIManager(config.api)
app = api_manager.create_app()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "framework": "ghost-backend"}

if __name__ == "__main__":
    api_manager.run()
```

### 4. Authentication
```python
from ghost import AuthManager, User, UserRole

# Initialize auth manager
auth_manager = AuthManager(config.auth)

# Create and authenticate users
user = User(
    id="user123",
    username="john_doe", 
    email="john@example.com",
    roles=[UserRole.USER]
)

# Hash password and create JWT token
hashed_password = auth_manager.hash_password("secure_password")
token = auth_manager.create_token(user)
```

## 🔧 Configuration

### Environment Variables (.env)
# 📚 Documentation

All project documentation is now located in the `docs/` folder for better organization and maintainability. This includes:
- Architecture Review: [docs/ARCHITECTURE_REVIEW.md](docs/ARCHITECTURE_REVIEW.md)
- Security Policy: [docs/SECURITY.md](docs/SECURITY.md)
- Security Status: [docs/SECURITY_STATUS_COMPLETE.md](docs/SECURITY_STATUS_COMPLETE.md)
- Security Setup: [docs/SECURITY_SETUP.md](docs/SECURITY_SETUP.md)
- API Management: [docs/API_MANAGEMENT.md](docs/API_MANAGEMENT.md)
- Contributing Guide: [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
- Proxy Configuration: [docs/PROXYMAN_FIX.md](docs/PROXYMAN_FIX.md)
- Security Remediation Report: [docs/SECURITY_REMEDIATION_REPORT.md](docs/SECURITY_REMEDIATION_REPORT.md)
- Organization Complete: [docs/ORGANIZATION_COMPLETE.md](docs/ORGANIZATION_COMPLETE.md)
```env
# Database
DATABASE_URL=postgresql://user:pass@localhost/dbname
REDIS_URL=redis://localhost:6379
MONGO_URL=mongodb://localhost:27017

# API

# Auth
JWT_SECRET_KEY=your-secret-key-here
# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# External APIs
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
```

### YAML Configuration (config.yaml)
```yaml
database:
  url: "postgresql://user:pass@localhost/dbname"
  pool_size: 5
  echo: false

api:
  title: "My API"
  version: "1.0.0"
  cors_origins: ["http://localhost:3000"]
  rate_limit: "100/minute"

logging:
  level: "INFO"
  file: "logs/app.log"
  rotation: "1 day"
  retention: "30 days"
```

## macOS setup via MacPorts (PostgreSQL 16)

- See docs/DATABASE_SETUP.md for step-by-step setup.
- Make targets: `db/install`, `db/init`, `db/start`, `env/keychain-setup`, `db/create`.
- Secrets are loaded from macOS Keychain at runtime. Optionally generate a local .env with `make env/dotenv-sync` (guarded; not recommended for long-term storage).

## 🧪 Testing

Run the test suite:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/ghost --cov-report=html

# Run specific test categories
pytest -m "not slow"  # Skip slow tests
pytest -m "unit"      # Only unit tests  
pytest -m "integration"  # Only integration tests
```

## 🔍 Development

### Setting up Development Environment
```bash
# Clone and setup
git clone <your-repo-url>
cd Ghost
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install

# Run development tools
black src/        # Format code
isort src/        # Sort imports
flake8 src/       # Lint code
mypy src/         # Type checking
```

### Code Quality
This framework enforces high code quality standards:
- **Black**: Code formatting
- **isort**: Import sorting  
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing with 85% coverage requirement

## 🎯 Design Principles

1. **Reusability First**: Every component is designed to be reused across multiple projects
2. **Configuration Driven**: Behavior is controlled through configuration, not code changes
3. **Optional Dependencies**: Core functionality doesn't require heavy dependencies
4. **Type Safety**: Full type hints and validation throughout
5. **Production Ready**: Includes logging, monitoring, error handling, and security
6. **Developer Experience**: Clear APIs, good documentation, helpful error messages

## 🏢 About Gray Ghost Data Consultants

This framework is developed and maintained by Gray Ghost Data Consultants, providing comprehensive backend solutions for modern applications.

---

**Ready to ghost your repetitive backend setup work?** 👻

Start building with the Ghost Backend Framework and focus on what makes your application unique, not the infrastructure around it.
