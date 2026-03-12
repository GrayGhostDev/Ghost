"""Tests for src/ghost/config.py"""

import json
import os
import pytest
import tempfile
from pathlib import Path

from src.ghost.config import (
    APIConfig,
    AuthConfig,
    Config,
    ConfigManager,
    DatabaseConfig,
    LoggingConfig,
    RedisConfig,
)


# ──────────────────────────────────────────────
# DatabaseConfig
# ──────────────────────────────────────────────

class TestDatabaseConfig:
    def test_url_generation(self):
        db = DatabaseConfig(host="db", port=5432, name="mydb", user="u", password="p")
        assert db.url == "postgresql://u:p@db:5432/mydb"

    def test_sqlite_url(self):
        db = DatabaseConfig(driver="sqlite", name="test.db")
        assert db.url == "sqlite:///test.db"

    def test_custom_url_override(self):
        db = DatabaseConfig()
        db.url = "postgresql://custom@host/db"
        assert db.url == "postgresql://custom@host/db"

    def test_custom_url_with_substitution_pattern(self):
        db = DatabaseConfig()
        db.url = "${DB_URL}"
        assert db.url == "${DB_URL}"

    def test_invalid_port_raises(self):
        with pytest.raises(ValueError, match="Invalid database port"):
            DatabaseConfig(port=0)

    def test_invalid_port_too_high(self):
        with pytest.raises(ValueError, match="Invalid database port"):
            DatabaseConfig(port=99999)

    def test_invalid_driver_raises(self):
        with pytest.raises(ValueError, match="Invalid database driver"):
            DatabaseConfig(driver="nosql")

    def test_invalid_custom_url_raises(self):
        db = DatabaseConfig()
        db.url = "ftp://bad-scheme"
        with pytest.raises(ValueError, match="Invalid database URL format"):
            _ = db.url


# ──────────────────────────────────────────────
# RedisConfig
# ──────────────────────────────────────────────

class TestRedisConfig:
    def test_url_no_password(self):
        r = RedisConfig(host="redis", port=6379, db=0)
        assert r.url == "redis://redis:6379/0"

    def test_url_with_password(self):
        r = RedisConfig(host="redis", port=6379, db=1, password="secret")
        assert r.url == "redis://:secret@redis:6379/1"


# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

class TestConfig:
    def test_default_values(self):
        c = Config()
        assert c.environment == "development"
        assert c.debug is True
        assert c.project_name == "Ghost Backend"

    def test_production_forces_debug_off(self):
        from src.ghost.config import AuthConfig
        auth = AuthConfig(jwt_secret="a-really-long-secure-secret-key-here")
        c = Config(environment="production", auth=auth)
        assert c.debug is False
        assert c.api.debug is False
        assert c.logging.level == "WARNING"

    def test_production_rejects_insecure_jwt(self):
        with pytest.raises(ValueError, match="JWT_SECRET must be set"):
            Config(environment="production")

    def test_testing_adjustments(self):
        c = Config(environment="testing")
        assert c.database.name.startswith("test_")
        assert c.redis.db == 1


# ──────────────────────────────────────────────
# ConfigManager — env loading
# ──────────────────────────────────────────────

class TestConfigManagerEnv:
    def test_load_from_env_defaults(self, monkeypatch, tmp_path):
        # Ensure no .env file interferes
        mgr = ConfigManager(config_dir=tmp_path)
        config = mgr.load_from_env()
        assert config.environment == "development"

    def test_env_var_overrides(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("PROJECT_NAME", "Test")
        monkeypatch.setenv("DB_HOST", "db-host")
        monkeypatch.setenv("DB_PORT", "5433")
        monkeypatch.setenv("API_HOST", "0.0.0.0")
        monkeypatch.setenv("API_PORT", "9000")
        monkeypatch.setenv("LOG_LEVEL", "ERROR")

        mgr = ConfigManager(config_dir=tmp_path)
        config = mgr.load_from_env()

        assert config.environment == "staging"
        assert config.debug is False
        assert config.project_name == "Test"
        assert config.database.host == "db-host"
        assert config.database.port == 5433
        assert config.api.host == "0.0.0.0"
        assert config.api.port == 9000
        assert config.logging.level == "ERROR"

    def test_database_url_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///override.db")
        mgr = ConfigManager(config_dir=tmp_path)
        config = mgr.load_from_env()
        assert config.database.url == "sqlite:///override.db"

    def test_jwt_secret_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("JWT_SECRET", "my-secret")
        mgr = ConfigManager(config_dir=tmp_path)
        config = mgr.load_from_env()
        assert config.auth.jwt_secret == "my-secret"
        assert config.api.jwt_secret == "my-secret"

    def test_log_json_toggle(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOG_JSON", "true")
        mgr = ConfigManager(config_dir=tmp_path)
        config = mgr.load_from_env()
        assert config.logging.json_output is True


# ──────────────────────────────────────────────
# ConfigManager — YAML loading
# ──────────────────────────────────────────────

class TestConfigManagerYAML:
    def test_load_from_yaml(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "environment: staging\n"
            "project_name: YAML Test\n"
            "database:\n"
            "  host: yaml-db\n"
            "  port: 5432\n"
            "  name: yamldb\n"
            "  user: u\n"
            "  password: p\n"
            "  driver: postgresql\n"
        )
        mgr = ConfigManager()
        config = mgr.load_from_yaml(yaml_file)
        assert config.environment == "staging"
        assert config.project_name == "YAML Test"
        assert config.database.host == "yaml-db"

    def test_yaml_file_not_found(self):
        mgr = ConfigManager()
        with pytest.raises(FileNotFoundError):
            mgr.load_from_yaml("/nonexistent/config.yaml")

    def test_save_to_yaml(self, tmp_path):
        mgr = ConfigManager()
        config = Config()
        out = tmp_path / "out.yaml"
        mgr.save_to_yaml(config, out)
        assert out.exists()
        loaded = mgr.load_from_yaml(out)
        assert loaded.environment == config.environment


# ──────────────────────────────────────────────
# ConfigManager — JSON loading
# ──────────────────────────────────────────────

class TestConfigManagerJSON:
    def test_load_from_json(self, tmp_path):
        json_file = tmp_path / "config.json"
        data = {
            "environment": "testing",
            "project_name": "JSON Test",
            "database": {
                "host": "json-db",
                "port": 5432,
                "name": "jsondb",
                "user": "u",
                "password": "p",
                "driver": "postgresql",
            },
        }
        json_file.write_text(json.dumps(data))

        mgr = ConfigManager()
        config = mgr.load_from_json(json_file)
        assert config.environment == "testing"
        assert config.project_name == "JSON Test"
        assert config.database.host == "json-db"

    def test_json_file_not_found(self):
        mgr = ConfigManager()
        with pytest.raises(FileNotFoundError):
            mgr.load_from_json("/nonexistent/config.json")


# ──────────────────────────────────────────────
# LoggingConfig
# ──────────────────────────────────────────────

class TestLoggingConfig:
    def test_file_sync(self):
        lc = LoggingConfig(file="test.log")
        assert lc.file_path == "test.log"

    def test_file_path_sync(self):
        lc = LoggingConfig(file_path="other.log")
        assert lc.file == "other.log"


# ──────────────────────────────────────────────
# AuthConfig defaults
# ──────────────────────────────────────────────

class TestAuthConfig:
    def test_defaults(self):
        ac = AuthConfig()
        assert ac.jwt_algorithm == "HS256"
        assert ac.password_min_length == 8
        assert ac.jwt_expiry_hours == 24
