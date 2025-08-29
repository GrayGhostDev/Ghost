"""
Ghost Backend Framework
A comprehensive backend development foundation for all projects.

This package provides common utilities, configurations, and patterns
for backend development across multiple projects.
"""

__version__ = "1.0.0"
__author__ = "Gray Ghost Data Consultants"
__description__ = "Comprehensive Backend Development Foundation"

# Make core modules easily accessible
from .config import Config, get_config, set_config, reload_config
from .logging import setup_logging, get_logger, LoggerMixin
from .utils import (
    DateTimeUtils, StringUtils, HashUtils, UUIDUtils,
    ValidationUtils, SerializationUtils, FileUtils,
    CacheUtils, DataStructureUtils, RetryUtils
)

# Import managers with error handling for optional dependencies
try:
    from .database import DatabaseManager, get_db_manager, get_db_session
    _DATABASE_AVAILABLE = True
except ImportError:
    _DATABASE_AVAILABLE = False

try:
    from .auth import AuthManager, User, UserRole, get_auth_manager
    _AUTH_AVAILABLE = True
except ImportError:
    _AUTH_AVAILABLE = False

try:
    from .api import APIManager, APIResponse, get_api_manager
    _API_AVAILABLE = True
except ImportError:
    _API_AVAILABLE = False

# Create conditional exports
__all__ = [
    "Config",
    "get_config", 
    "set_config",
    "reload_config",
    "setup_logging",
    "get_logger",
    "LoggerMixin",
    "DateTimeUtils",
    "StringUtils", 
    "HashUtils",
    "UUIDUtils",
    "ValidationUtils",
    "SerializationUtils",
    "FileUtils",
    "CacheUtils",
    "DataStructureUtils",
    "RetryUtils",
]

if _DATABASE_AVAILABLE:
    __all__.extend([
        "DatabaseManager",
        "get_db_manager", 
        "get_db_session"
    ])

if _AUTH_AVAILABLE:
    __all__.extend([
        "AuthManager",
        "User",
        "UserRole", 
        "get_auth_manager"
    ])

if _API_AVAILABLE:
    __all__.extend([
        "APIManager",
        "APIResponse", 
        "get_api_manager"
    ])

# Convenience function to check available features
def get_available_features():
    """Get list of available features based on installed dependencies."""
    features = {
        "config": True,
        "logging": True, 
        "utils": True,
        "database": _DATABASE_AVAILABLE,
        "auth": _AUTH_AVAILABLE,
        "api": _API_AVAILABLE,
    }
    return features
