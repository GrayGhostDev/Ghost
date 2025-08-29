"""
Authentication Module

Provides JWT-based authentication, user management, and authorization utilities.
Supports role-based access control (RBAC) and API key authentication.
"""

import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
from enum import Enum
from .config import get_config
from .logging import get_logger, LoggerMixin


class UserRole(Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    API = "api"


@dataclass
class User:
    """User data class."""
    id: str
    username: str
    email: str
    roles: List[UserRole]
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class TokenData:
    """JWT token data."""
    user_id: str
    username: str
    roles: List[str]
    exp: Optional[datetime]
    iat: datetime
    type: str = "access"


class AuthManager(LoggerMixin):
    """Manages authentication and authorization."""
    
    def __init__(self, config=None):
        self.config = config or get_config().auth  # Use auth config, not api config
        self.secret_key = self.config.jwt_secret
        self.algorithm = self.config.jwt_algorithm
        self.expiry_hours = self.config.jwt_expiry_hours
        
        if not self.secret_key:
            raise ValueError("JWT secret key not configured")
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Password verification error: {e}")
            return False
    
    def create_access_token(
        self, 
        user: User, 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=self.expiry_hours)
        
        payload = {
            "sub": user.id,
            "username": user.username,
            "roles": [role.value for role in user.roles],
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        self.logger.debug(f"Access token created for user {user.username}")
        return token
    
    def create_refresh_token(self, user: User) -> str:
        """Create a JWT refresh token with longer expiration."""
        expire = datetime.utcnow() + timedelta(days=30)
        
        payload = {
            "sub": user.id,
            "username": user.username,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        self.logger.debug(f"Refresh token created for user {user.username}")
        return token
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            token_data = TokenData(
                user_id=payload["sub"],
                username=payload["username"],
                roles=payload.get("roles", []),
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"]),
                type=payload.get("type", "access")
            )
            
            return token_data
            
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            self.logger.warning(f"Invalid token: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Generate new access token from refresh token."""
        token_data = self.verify_token(refresh_token)
        
        if not token_data or token_data.type != "refresh":
            return None
        
        # Create a minimal user object for token generation
        user = User(
            id=token_data.user_id,
            username=token_data.username,
            email="",  # Not stored in refresh token
            roles=[UserRole(role) for role in token_data.roles]
        )
        
        return self.create_access_token(user)
    
    def check_permissions(
        self, 
        token_data: TokenData, 
        required_roles: List[UserRole]
    ) -> bool:
        """Check if user has required permissions."""
        user_roles = [UserRole(role) for role in token_data.roles]
        
        # Admin has access to everything
        if UserRole.ADMIN in user_roles:
            return True
        
        # Check if user has any of the required roles
        return any(role in user_roles for role in required_roles)
    
    def generate_api_key(self, user: User, name: str) -> str:
        """Generate an API key for a user."""
        payload = {
            "sub": user.id,
            "username": user.username,
            "roles": [role.value for role in user.roles],
            "key_name": name,
            "type": "api_key",
            "iat": datetime.utcnow(),
            # API keys don't expire by default
        }
        
        api_key = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        self.logger.info(f"API key generated for user {user.username}: {name}")
        return api_key
    
    def verify_api_key(self, api_key: str) -> Optional[TokenData]:
        """Verify an API key."""
        try:
            payload = jwt.decode(api_key, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get("type") != "api_key":
                return None
            
            token_data = TokenData(
                user_id=payload["sub"],
                username=payload["username"],
                roles=payload.get("roles", []),
                exp=datetime.fromtimestamp(payload.get("exp", 0)) if payload.get("exp") else None,
                iat=datetime.fromtimestamp(payload["iat"]),
                type="api_key"
            )
            
            return token_data
            
        except jwt.InvalidTokenError as e:
            self.logger.warning(f"Invalid API key: {e}")
            return None


class RoleBasedAccessControl:
    """Role-based access control utilities."""
    
    ROLE_HIERARCHY = {
        UserRole.ADMIN: [UserRole.ADMIN, UserRole.USER, UserRole.GUEST, UserRole.API],
        UserRole.USER: [UserRole.USER, UserRole.GUEST],
        UserRole.GUEST: [UserRole.GUEST],
        UserRole.API: [UserRole.API],
    }
    
    @classmethod
    def has_permission(cls, user_roles: List[UserRole], required_role: UserRole) -> bool:
        """Check if user roles include required permission level."""
        for user_role in user_roles:
            if required_role in cls.ROLE_HIERARCHY.get(user_role, []):
                return True
        return False
    
    @classmethod
    def get_accessible_roles(cls, user_role: UserRole) -> List[UserRole]:
        """Get all roles accessible by the given role."""
        return cls.ROLE_HIERARCHY.get(user_role, [])


def require_auth(required_roles: Optional[List[UserRole]] = None):
    """Decorator to require authentication for functions."""
    if required_roles is None:
        required_roles = [UserRole.USER]
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            # In a real implementation, you'd extract the token from the request
            # This is a simplified example
            token = kwargs.get('auth_token')
            if not token:
                raise ValueError("Authentication required")
            
            auth_manager = AuthManager()
            token_data = auth_manager.verify_token(token)
            
            if not token_data:
                raise ValueError("Invalid authentication token")
            
            if not auth_manager.check_permissions(token_data, required_roles):
                raise ValueError("Insufficient permissions")
            
            # Add token data to kwargs for use in the function
            kwargs['current_user'] = token_data
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_api_key():
    """Decorator to require API key authentication."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            api_key = kwargs.get('api_key')
            if not api_key:
                raise ValueError("API key required")
            
            auth_manager = AuthManager()
            token_data = auth_manager.verify_api_key(api_key)
            
            if not token_data:
                raise ValueError("Invalid API key")
            
            kwargs['current_user'] = token_data
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Global auth manager instance
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get the global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager
