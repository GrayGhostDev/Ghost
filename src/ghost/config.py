"""
Configuration Management Module

Centralized configuration handling for all backend projects.
Supports environment variables, YAML files, and runtime configuration.
"""

import json
import logging
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field, fields
from dotenv import load_dotenv

_config_logger = logging.getLogger(__name__)


def _get_int_env(key: str, default: int) -> int:
    """Read an integer environment variable with a safe fallback on bad values."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        _config_logger.warning(
            "Invalid integer value for env var %s=%r — using default %d", key, val, default
        )
        return default


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

    def __post_init__(self):
        """Validate database configuration."""
        # Validate port number
        if not isinstance(self.port, int) or self.port < 1 or self.port > 65535:
            raise ValueError(
                f"Invalid database port: {self.port}. Must be between 1 and 65535."
            )

        # Validate driver
        valid_drivers = ["postgresql", "postgres", "mysql", "sqlite", "oracle", "mssql"]
        if self.driver not in valid_drivers:
            raise ValueError(
                f"Invalid database driver: {self.driver}. Must be one of {valid_drivers}"
            )

    @property
    def url(self) -> str:
        """Generate database connection URL."""
        if self._custom_url:
            # Allow flexible URL formats for testing and environment substitution
            # Only validate if it looks like a complete URL (contains ://)
            if "://" in self._custom_url:
                valid_prefixes = (
                    "postgresql://",
                    "postgres://",
                    "mysql://",
                    "sqlite://",
                    "oracle://",
                    "mssql://",
                )
                if not self._custom_url.startswith(valid_prefixes):
                    # Allow URLs with substitution patterns like ${DB_HOST} or ***
                    if not any(
                        pattern in self._custom_url
                        for pattern in ["${", "***", "%(", "{{"]
                    ):
                        raise ValueError(
                            f"Invalid database URL format: {self._custom_url}"
                        )
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
    format: str = (
        "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
    )
    json_output: bool = False  # Enable JSON structured logs (for Loki/Promtail)
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
            # Validate JWT secret is not the default in production
            insecure_defaults = {
                "dev-secret-key-change-in-production",
                "change-this-to-a-long-random-string",
                "",
            }
            if self.auth.jwt_secret in insecure_defaults:
                raise ValueError(
                    "JWT_SECRET must be set to a secure value in production. "
                    "Set the JWT_SECRET environment variable."
                )
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
        config.database.port = _get_int_env("DB_PORT", config.database.port)
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
        config.redis.port = _get_int_env("REDIS_PORT", config.redis.port)
        config.redis.db = _get_int_env("REDIS_DB", config.redis.db)
        config.redis.password = os.getenv("REDIS_PASSWORD", config.redis.password)

        # API settings
        config.api.host = os.getenv("API_HOST", config.api.host)
        config.api.port = _get_int_env("API_PORT", config.api.port)
        config.api.api_key = os.getenv("API_KEY", config.api.api_key)
        config.api.jwt_secret = os.getenv("JWT_SECRET", config.api.jwt_secret)

        # External APIs
        config.external_apis.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        config.external_apis.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        config.external_apis.github_token = os.getenv("GITHUB_TOKEN", "")
        config.external_apis.sentry_dsn = os.getenv("SENTRY_DSN", "")

        # Auth settings
        jwt_secret = os.getenv("JWT_SECRET")
        if jwt_secret:
            config.auth.jwt_secret = jwt_secret

        # Logging settings (support LOG_LEVEL and LOG_JSON overrides)
        config.logging.level = os.getenv("LOG_LEVEL", config.logging.level)
        if os.getenv("LOG_JSON", "").lower() in ("1", "true", "yes"):
            config.logging.json_output = True

        # Optional GCP Secret Manager overlay
        gcp_project = os.getenv("GCP_SECRET_PROJECT")
        if gcp_project:
            try:
                from ghost.gcp_secrets import GCPSecretManager

                gcp = GCPSecretManager(gcp_project)
                gcp.overlay_config(config)
            except Exception as _gcp_exc:
                _config_logger.warning(
                    "GCP Secret Manager overlay failed (project=%s): %s — "
                    "continuing with env-var values",
                    gcp_project, _gcp_exc
                )

        return config

    def load_from_yaml(self, file_path: Union[str, Path]) -> Config:
        """Load configuration from YAML file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

        # Convert nested dict to Config object
        config = self._dict_to_config(data)
        return config

    @staticmethod
    def _filter_dataclass_fields(dc_class, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return only keys from data that are valid fields of the dataclass.

        Unknown keys are logged as warnings rather than raising TypeError.
        """
        valid = {f.name for f in fields(dc_class)}
        filtered = {k: v for k, v in data.items() if k in valid}
        unknown = set(data) - valid
        if unknown:
            _config_logger.warning(
                "Unknown key(s) in %s config (ignored): %s",
                dc_class.__name__, ", ".join(sorted(unknown))
            )
        return filtered

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
            known = self._filter_dataclass_fields(
                DatabaseConfig, {k: v for k, v in db_data.items() if k != "url"}
            )
            config.database = DatabaseConfig(**known)
            # Always apply url override last
            if "url" in db_data:
                config.database.url = db_data["url"]

        # Redis
        if "redis" in data:
            config.redis = RedisConfig(
                **self._filter_dataclass_fields(RedisConfig, data["redis"])
            )

        # API
        if "api" in data:
            config.api = APIConfig(
                **self._filter_dataclass_fields(APIConfig, data["api"])
            )

        # Logging
        if "logging" in data:
            config.logging = LoggingConfig(
                **self._filter_dataclass_fields(LoggingConfig, data["logging"])
            )

        # External APIs
        if "external_apis" in data:
            config.external_apis = ExternalAPIsConfig(
                **self._filter_dataclass_fields(ExternalAPIsConfig, data["external_apis"])
            )

        # Custom settings
        config.custom = data.get("custom", {})

        return config

    def load_from_json(self, file_path: Union[str, Path]) -> Config:
        """Load configuration from JSON file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with open(file_path, "r") as f:
            data = json.load(f)

        config = self._dict_to_config(data)
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

        with open(file_path, "w") as f:
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
