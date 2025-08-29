"""
Configuration Management Module

Centralized configuration handling for all backend projects.
Supports environment variables, YAML files, and runtime configuration.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    host: str = "localhost"
    port: int = 5432
    name: str = "ghost_db"
    user: str = "postgres"
    password: str = ""
    driver: str = "postgresql"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False
    _custom_url: Optional[str] = field(default=None, init=False)
    
    @property
    def url(self) -> str:
        """Generate database connection URL."""
        if self._custom_url:
            return self._custom_url
        if self.driver == "sqlite":
            return f"sqlite:///{self.name}"
        return f"{self.driver}://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
    
    @url.setter
    def url(self, value: str) -> None:
        """Set custom database URL."""
        self._custom_url = value


@dataclass
class RedisConfig:
    """Redis configuration settings."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    decode_responses: bool = True
    
    @property
    def url(self) -> str:
        """Generate Redis connection URL."""
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


@dataclass
class APIConfig:
    """API configuration settings."""
    host: str = "127.0.0.1"  # Default to localhost for security
    port: int = 8000
    title: str = "Ghost Backend API"  # Add title property
    version: str = "1.0.0"  # Add version property
    debug: bool = False
    reload: bool = False
    workers: int = 1
    cors_origins: list = field(default_factory=lambda: ["*"])
    rate_limit: str = "100/minute"
    api_key: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24


@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    level: str = "INFO"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
    file: Optional[str] = None  # Add file property (alias for file_path)
    file_path: Optional[str] = None
    max_size: str = "10 MB"
    retention: str = "30 days"
    compression: str = "zip"
    
    def __post_init__(self):
        """Sync file and file_path properties."""
        if self.file and not self.file_path:
            self.file_path = self.file
        elif self.file_path and not self.file:
            self.file = self.file_path


@dataclass
class ExternalAPIsConfig:
    """External API configuration."""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    github_token: str = ""
    sentry_dsn: str = ""


@dataclass

@dataclass
class AuthConfig:
    """Authentication configuration settings."""
    jwt_secret: str = "dev-secret-key-change-in-production"  # Add default for testing
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    jwt_expiry_hours: int = 24  # Add this missing attribute
    password_min_length: int = 8


@dataclass
class Config:
    """Main configuration class."""
    environment: str = "development"
    debug: bool = True
    project_name: str = "Ghost Backend"
    version: str = "1.0.0"
    
    # Sub-configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    api: APIConfig = field(default_factory=APIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    external_apis: ExternalAPIsConfig = field(default_factory=ExternalAPIsConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    
    # Custom settings
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization setup."""
        if self.environment == "production":
            self.debug = False
            self.api.debug = False
            self.logging.level = "WARNING"
        elif self.environment == "testing":
            self.database.name = "test_" + self.database.name
            self.redis.db = 1


class ConfigManager:
    """Configuration manager with multiple loading strategies."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.cwd()
        self._config: Optional[Config] = None
    
    def load_from_env(self) -> Config:
        """Load configuration from environment variables."""
        # Load .env file if it exists
        env_file = self.config_dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)
        
        config = Config()
        
        # Basic settings
        config.environment = os.getenv("ENVIRONMENT", config.environment)
        config.debug = os.getenv("DEBUG", str(config.debug)).lower() == "true"
        config.project_name = os.getenv("PROJECT_NAME", config.project_name)
        config.version = os.getenv("VERSION", config.version)
        
        # Database settings
        config.database.host = os.getenv("DB_HOST", config.database.host)
        config.database.port = int(os.getenv("DB_PORT", config.database.port))
        config.database.name = os.getenv("DB_NAME", config.database.name)
        config.database.user = os.getenv("DB_USER", config.database.user)
        config.database.password = os.getenv("DB_PASSWORD", config.database.password)
        config.database.driver = os.getenv("DB_DRIVER", config.database.driver)
        # Always apply DATABASE_URL override last
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            config.database.url = db_url
        
        # Redis settings
        config.redis.host = os.getenv("REDIS_HOST", config.redis.host)
        config.redis.port = int(os.getenv("REDIS_PORT", config.redis.port))
        config.redis.db = int(os.getenv("REDIS_DB", config.redis.db))
        config.redis.password = os.getenv("REDIS_PASSWORD", config.redis.password)
        
        # API settings
        config.api.host = os.getenv("API_HOST", config.api.host)
        config.api.port = int(os.getenv("API_PORT", config.api.port))
        config.api.api_key = os.getenv("API_KEY", config.api.api_key)
        config.api.jwt_secret = os.getenv("JWT_SECRET", config.api.jwt_secret)
        
        # External APIs
        config.external_apis.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        config.external_apis.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        config.external_apis.github_token = os.getenv("GITHUB_TOKEN", "")
        config.external_apis.sentry_dsn = os.getenv("SENTRY_DSN", "")
        
        # Logging settings (support LOG_LEVEL override)
        config.logging.level = os.getenv("LOG_LEVEL", config.logging.level)
        return config
    
    def load_from_yaml(self, file_path: Union[str, Path]) -> Config:
        """Load configuration from YAML file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Convert nested dict to Config object
        config = self._dict_to_config(data)
        return config
    
    def _dict_to_config(self, data: Dict[str, Any]) -> Config:
        """Convert dictionary to Config object."""
        config = Config()
        
        # Basic settings
        config.environment = data.get("environment", config.environment)
        config.debug = data.get("debug", config.debug)
        config.project_name = data.get("project_name", config.project_name)
        config.version = data.get("version", config.version)
        
        # Database
        if "database" in data:
            db_data = data["database"]
            config.database = DatabaseConfig(**{k: v for k, v in db_data.items() if k != "url"})
            # Always apply url override last
            if "url" in db_data:
                config.database.url = db_data["url"]
        
        # Redis
        if "redis" in data:
            redis_data = data["redis"]
            config.redis = RedisConfig(**redis_data)
        
        # API
        if "api" in data:
            api_data = data["api"]
            config.api = APIConfig(**api_data)
        
        # Logging
        if "logging" in data:
            log_data = data["logging"]
            config.logging = LoggingConfig(**log_data)
        
        # External APIs
        if "external_apis" in data:
            ext_data = data["external_apis"]
            config.external_apis = ExternalAPIsConfig(**ext_data)
        
        # Custom settings
        config.custom = data.get("custom", {})
        
        return config
    
    def save_to_yaml(self, config: Config, file_path: Union[str, Path]) -> None:
        """Save configuration to YAML file."""
        file_path = Path(file_path)
        
        # Convert Config to dict
        data = {
            "environment": config.environment,
            "debug": config.debug,
            "project_name": config.project_name,
            "version": config.version,
            "database": {
                "host": config.database.host,
                "port": config.database.port,
                "name": config.database.name,
                "user": config.database.user,
                "password": config.database.password,
                "driver": config.database.driver,
                "pool_size": config.database.pool_size,
                "max_overflow": config.database.max_overflow,
                "echo": config.database.echo,
            },
            "redis": {
                "host": config.redis.host,
                "port": config.redis.port,
                "db": config.redis.db,
                "password": config.redis.password,
                "decode_responses": config.redis.decode_responses,
            },
            "api": {
                "host": config.api.host,
                "port": config.api.port,
                "debug": config.api.debug,
                "reload": config.api.reload,
                "workers": config.api.workers,
                "cors_origins": config.api.cors_origins,
                "rate_limit": config.api.rate_limit,
                "api_key": config.api.api_key,
                "jwt_secret": config.api.jwt_secret,
                "jwt_algorithm": config.api.jwt_algorithm,
                "jwt_expiry_hours": config.api.jwt_expiry_hours,
            },
            "logging": {
                "level": config.logging.level,
                "format": config.logging.format,
                "file_path": config.logging.file_path,
                "max_size": config.logging.max_size,
                "retention": config.logging.retention,
                "compression": config.logging.compression,
            },
            "external_apis": {
                "openai_api_key": config.external_apis.openai_api_key,
                "anthropic_api_key": config.external_apis.anthropic_api_key,
                "github_token": config.external_apis.github_token,
                "sentry_dsn": config.external_apis.sentry_dsn,
            },
            "custom": config.custom,
        }
        
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)


# Global configuration instance
_config_manager = ConfigManager()
_global_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _global_config
    if _global_config is None:
        _global_config = _config_manager.load_from_env()
    return _global_config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _global_config
    _global_config = config


def reload_config() -> Config:
    """Reload configuration from environment."""
    global _global_config
    _global_config = _config_manager.load_from_env()
    return _global_config
