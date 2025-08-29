# Ghost Backend Framework - Example Usage

This directory contains example usage patterns and templates for the Ghost backend framework.

## Quick Start

```python
from ghost import Config, get_config, setup_logging, get_logger
from ghost.database import get_db_manager, Base
from ghost.api import get_api_manager, APIResponse
from ghost.auth import AuthManager, User, UserRole
from ghost.utils import StringUtils, DateTimeUtils

# 1. Setup logging
setup_logging()
logger = get_logger("myapp")

# 2. Initialize database
db_manager = get_db_manager()
db_manager.initialize()
db_manager.create_tables()

# 3. Create FastAPI app
api_manager = get_api_manager()
app = api_manager.create_app(title="My Backend API")

# 4. Add your routes
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

@router.get("/users")
async def list_users():
    return APIResponse.success(data=[], message="Users retrieved")

app.include_router(router)

# 5. Run the server
if __name__ == "__main__":
    api_manager.run()
```

## Configuration Examples

### Environment Variables (.env)
```
ENVIRONMENT=development
DEBUG=true
PROJECT_NAME=My Backend API

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp_db
DB_USER=postgres
DB_PASSWORD=password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# API
API_HOST=0.0.0.0
API_PORT=8000
JWT_SECRET=your-secret-key-here

# External APIs
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
```

### YAML Configuration (config.yaml)
```yaml
environment: development
debug: true
project_name: My Backend API
version: 1.0.0

database:
  host: localhost
  port: 5432
  name: myapp_db
  user: postgres
  password: password
  driver: postgresql
  pool_size: 10

redis:
  host: localhost
  port: 6379
  db: 0

api:
  host: 0.0.0.0
  port: 8000
  debug: true
  cors_origins: ["*"]
  jwt_secret: your-secret-key-here

logging:
  level: INFO
  file_path: logs/app.log

external_apis:
  openai_api_key: your-openai-key
  anthropic_api_key: your-anthropic-key

custom:
  feature_flags:
    new_feature: true
  limits:
    max_requests_per_minute: 100
```

## Database Usage Examples

### Define Models
```python
from ghost.database import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Database Operations
```python
from ghost.database import get_db_session

# Create user
with get_db_session() as session:
    user = User(username="john", email="john@example.com")
    session.add(user)
    session.commit()

# Query users
with get_db_session() as session:
    users = session.query(User).filter(User.is_active == True).all()
```

## API Usage Examples

### Protected Routes
```python
from fastapi import Depends
from ghost.api import get_api_manager
from ghost.auth import UserRole

api_manager = get_api_manager()

@router.get("/protected")
async def protected_route(current_user = Depends(api_manager.require_auth)):
    return APIResponse.success(data={"user": current_user.username})

@router.get("/admin-only")
async def admin_route(current_user = Depends(api_manager.require_auth)):
    if UserRole.ADMIN not in [UserRole(role) for role in current_user.roles]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return APIResponse.success(message="Admin access granted")
```

### Rate Limited Routes
```python
from slowapi import Limiter
from ghost.api import get_api_manager

api_manager = get_api_manager()

@router.get("/limited")
@api_manager.limiter.limit("5/minute")
async def limited_route(request: Request):
    return APIResponse.success(message="Rate limited endpoint")
```

## Authentication Examples

### User Registration and Login
```python
from ghost.auth import AuthManager, User, UserRole
from ghost.database import get_db_session

auth_manager = AuthManager()

# Register user
async def register_user(username: str, email: str, password: str):
    hashed_password = auth_manager.hash_password(password)
    
    with get_db_session() as session:
        user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            roles=[UserRole.USER]
        )
        session.add(user)
        session.commit()
    
    return user

# Login user
async def login_user(username: str, password: str):
    with get_db_session() as session:
        user = session.query(User).filter(User.username == username).first()
        
        if not user or not auth_manager.verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
        
        access_token = auth_manager.create_access_token(user)
        refresh_token = auth_manager.create_refresh_token(user)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user
        }
```

## Utility Examples

### Data Validation
```python
from ghost.utils import ValidationUtils, StringUtils

# Validate API payload
required_fields = ["name", "email", "password"]
missing = ValidationUtils.validate_required_fields(data, required_fields)

if missing:
    raise ValueError(f"Missing fields: {missing}")

# Generate secure password
password = StringUtils.generate_random_string(12, include_special=True)

# Create slug from title
slug = StringUtils.generate_slug("My Blog Post Title")  # "my-blog-post-title"
```

### Caching with Redis
```python
from ghost.database import get_redis_manager
from ghost.utils import CacheUtils, SerializationUtils

redis_manager = get_redis_manager()

# Cache data
cache_key = CacheUtils.generate_cache_key("users", page=1, limit=10)
data = {"users": [...]}
redis_manager.set(cache_key, SerializationUtils.to_json(data), expire=300)

# Retrieve cached data
cached_data = redis_manager.get(cache_key)
if cached_data:
    data = SerializationUtils.from_json(cached_data)
```

## Background Tasks

### Celery Integration
```python
from celery import Celery
from ghost import setup_logging, get_config

# Setup Celery
config = get_config()
celery_app = Celery(
    'ghost-tasks',
    broker=config.redis.url,
    backend=config.redis.url
)

@celery_app.task
def process_data_task(data_id: str):
    setup_logging()  # Setup logging in task
    logger = get_logger("tasks")
    
    # Process data
    logger.info(f"Processing data: {data_id}")
    # Your processing logic here
    
    return {"status": "completed", "data_id": data_id}
```

## Testing Examples

### Unit Tests
```python
import pytest
from ghost import get_config, setup_logging
from ghost.database import get_db_manager, Base
from ghost.auth import AuthManager, User, UserRole

@pytest.fixture
def test_config():
    config = get_config()
    config.environment = "testing"
    config.database.name = "test_db"
    return config

@pytest.fixture
def db_session():
    db_manager = get_db_manager()
    db_manager.initialize()
    Base.metadata.create_all(bind=db_manager.engine)
    
    with db_manager.get_session() as session:
        yield session
    
    Base.metadata.drop_all(bind=db_manager.engine)

def test_user_creation(db_session):
    auth_manager = AuthManager()
    
    user = User(
        id="test-id",
        username="testuser",
        email="test@example.com",
        roles=[UserRole.USER]
    )
    
    token = auth_manager.create_access_token(user)
    assert token is not None
    
    token_data = auth_manager.verify_token(token)
    assert token_data.username == "testuser"
```

## Deployment Examples

### Docker
```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DB_HOST=postgres
      - REDIS_HOST=redis
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: myapp_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```
