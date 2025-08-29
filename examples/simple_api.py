"""
Simple FastAPI Application Example

This example demonstrates how to create a basic FastAPI application
using the Ghost backend framework.
"""

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from ghost import setup_logging, get_logger, get_config
from ghost.api import get_api_manager, APIResponse
from ghost.auth import get_auth_manager, User, UserRole
from ghost.database import get_db_manager, get_db_session
from ghost.utils import ValidationUtils, StringUtils, DateTimeUtils
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

# Setup logging
setup_logging()
logger = get_logger("example_app")

# Get managers
config = get_config()
api_manager = get_api_manager()
auth_manager = get_auth_manager()
db_manager = get_db_manager()

# Pydantic models for request/response
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    roles: List[str]
    is_active: bool
    created_at: str

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserResponse

# Create FastAPI app
app = api_manager.create_app(
    title="Ghost Example API",
    description="Example application using Ghost backend framework",
    version="1.0.0"
)

# Initialize database
db_manager.initialize()
logger.info("Database initialized")

# Routes
@app.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate):
    """Register a new user."""
    
    # Validate input
    if not StringUtils.is_valid_email(user_data.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    if len(user_data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Check if user already exists
    with get_db_session() as session:
        # In a real app, you'd query your user table here
        pass
    
    # Create user
    user_id = StringUtils.generate_random_string(16)
    hashed_password = auth_manager.hash_password(user_data.password)
    
    user = User(
        id=user_id,
        username=user_data.username,
        email=user_data.email,
        roles=[UserRole.USER],
        created_at=DateTimeUtils.now_utc()
    )
    
    # In a real app, save to database here
    logger.info(f"User registered: {user.username}")
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        roles=[role.value for role in user.roles],
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else ""
    )

@app.post("/login", response_model=dict)
async def login_user(login_data: LoginRequest):
    """Login user and return tokens."""
    
    # In a real app, fetch user from database
    # For demo, create a mock user
    if login_data.username == "demo" and login_data.password == "password123":
        user = User(
            id="demo-user",
            username="demo",
            email="demo@example.com",
            roles=[UserRole.USER]
        )
        
        access_token = auth_manager.create_access_token(user)
        refresh_token = auth_manager.create_refresh_token(user)
        
        return APIResponse.success(
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "roles": [role.value for role in user.roles]
                }
            },
            message="Login successful"
        )
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/profile")
async def get_profile(current_user = Depends(api_manager.require_auth)):
    """Get current user profile (requires authentication)."""
    
    return APIResponse.success(
        data={
            "id": current_user.user_id,
            "username": current_user.username,
            "roles": current_user.roles
        },
        message="Profile retrieved successfully"
    )

@app.get("/admin-only")
async def admin_only_endpoint(current_user = Depends(api_manager.require_auth)):
    """Admin-only endpoint."""
    
    if UserRole.ADMIN.value not in current_user.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return APIResponse.success(
        data={"message": "Welcome, admin!"},
        message="Admin access granted"
    )

@app.get("/rate-limited")
@api_manager.limiter.limit("5/minute")
async def rate_limited_endpoint(request: Request):
    """Rate limited endpoint (5 requests per minute)."""
    
    return APIResponse.success(
        data={"timestamp": DateTimeUtils.now_utc().isoformat()},
        message="This endpoint is rate limited to 5 requests per minute"
    )

@app.get("/utils-demo")
async def utils_demo():
    """Demonstrate utility functions."""
    
    # Generate random data
    random_string = StringUtils.generate_random_string(8)
    slug = StringUtils.generate_slug("Hello World Example!")
    masked_email = StringUtils.mask_sensitive("user@example.com", show_last=7)
    
    # Date utilities
    now = DateTimeUtils.now_utc()
    timestamp = DateTimeUtils.to_timestamp(now)
    
    return APIResponse.success(
        data={
            "random_string": random_string,
            "slug": slug,
            "masked_email": masked_email,
            "current_time": now.isoformat(),
            "timestamp": timestamp
        },
        message="Utility functions demonstrated"
    )

if __name__ == "__main__":
    # Run the application
    logger.info(f"Starting application on {config.api.host}:{config.api.port}")
    
    uvicorn.run(
        app,
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
        log_level="info"
    )
