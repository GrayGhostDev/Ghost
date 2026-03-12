"""Shared test fixtures for Ghost Backend test suite."""

import pytest
from pathlib import Path
from unittest.mock import patch

from src.ghost.config import Config, AuthConfig, APIConfig, set_config


@pytest.fixture(autouse=True)
def _reset_global_config():
    """Reset global config singleton between tests."""
    import src.ghost.config as config_mod
    import src.ghost.auth as auth_mod
    import src.ghost.api as api_mod
    import src.ghost.logging as log_mod

    # Save originals
    orig_config = config_mod._global_config
    orig_auth = auth_mod._auth_manager
    orig_api = api_mod._api_manager
    orig_log_configured = log_mod._logging_manager._configured

    yield

    # Restore
    config_mod._global_config = orig_config
    auth_mod._auth_manager = orig_auth
    api_mod._api_manager = orig_api
    log_mod._logging_manager._configured = orig_log_configured


@pytest.fixture
def test_config():
    """Clean Config with environment='testing' and safe JWT secret."""
    config = Config(
        environment="testing",
        debug=True,
        project_name="Ghost Test",
    )
    config.auth.jwt_secret = "test-secret-key-for-unit-tests-only"
    set_config(config)
    return config


@pytest.fixture
def auth_config():
    """Isolated AuthConfig for auth tests."""
    return AuthConfig(
        jwt_secret="test-auth-secret-key-minimum-length",
        jwt_algorithm="HS256",
        jwt_expiry_hours=1,
        password_min_length=8,
    )


@pytest.fixture
def api_config():
    """Isolated APIConfig for API tests."""
    return APIConfig(
        host="127.0.0.1",
        port=8000,
        debug=True,
        cors_origins=["*"],
        rate_limit="100/minute",
        jwt_secret="test-api-secret-key",
        jwt_algorithm="HS256",
        jwt_expiry_hours=1,
    )


@pytest.fixture
def make_user():
    """Factory fixture returning auth.User dataclass instances."""
    from src.ghost.auth import User, UserRole

    def _make(
        id="user-1",
        username="testuser",
        email="test@example.com",
        roles=None,
        is_active=True,
    ):
        if roles is None:
            roles = [UserRole.USER]
        return User(
            id=id,
            username=username,
            email=email,
            roles=roles,
            is_active=is_active,
        )

    return _make


@pytest.fixture
def tmp_storage(tmp_path):
    """LocalStorageProvider backed by tmp_path."""
    from src.ghost.storage import LocalStorageProvider

    return LocalStorageProvider(
        base_path=str(tmp_path / "uploads"),
        public_url_base="/files",
    )
