"""Tests for src/ghost/auth.py"""

import time
import pytest
from datetime import timedelta
from unittest.mock import patch

from src.ghost.auth import (
    AuthManager,
    RoleBasedAccessControl,
    TokenData,
    User,
    UserRole,
)


class TestPasswordHashing:
    """Tests for hash_password / verify_password."""

    def test_hash_password_returns_string(self, auth_config):
        mgr = AuthManager(auth_config)
        hashed = mgr.hash_password("secret123")
        assert isinstance(hashed, str)
        assert hashed != "secret123"

    def test_hash_password_different_each_time(self, auth_config):
        mgr = AuthManager(auth_config)
        h1 = mgr.hash_password("same")
        h2 = mgr.hash_password("same")
        assert h1 != h2  # unique salts

    def test_verify_password_correct(self, auth_config):
        mgr = AuthManager(auth_config)
        hashed = mgr.hash_password("correct")
        assert mgr.verify_password("correct", hashed) is True

    def test_verify_password_wrong(self, auth_config):
        mgr = AuthManager(auth_config)
        hashed = mgr.hash_password("correct")
        assert mgr.verify_password("wrong", hashed) is False

    def test_verify_password_invalid_hash(self, auth_config):
        mgr = AuthManager(auth_config)
        assert mgr.verify_password("pw", "not-a-bcrypt-hash") is False


class TestAccessToken:
    """Tests for create_access_token / verify_token."""

    def test_create_and_verify_access_token(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user()
        token = mgr.create_access_token(user)
        data = mgr.verify_token(token)

        assert data is not None
        assert data.user_id == user.id
        assert data.username == user.username
        assert data.type == "access"
        assert "user" in data.roles

    def test_access_token_custom_expiry(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user()
        token = mgr.create_access_token(user, expires_delta=timedelta(minutes=5))
        data = mgr.verify_token(token)
        assert data is not None

    def test_access_token_expired(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user()
        token = mgr.create_access_token(user, expires_delta=timedelta(seconds=-1))
        assert mgr.verify_token(token) is None

    def test_verify_token_invalid(self, auth_config):
        mgr = AuthManager(auth_config)
        assert mgr.verify_token("garbage.token.here") is None


class TestRefreshToken:
    """Tests for create_refresh_token / refresh_access_token."""

    def test_create_and_verify_refresh_token(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user()
        token = mgr.create_refresh_token(user)
        data = mgr.verify_token(token)

        assert data is not None
        assert data.type == "refresh"
        assert data.user_id == user.id

    def test_refresh_access_token(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user()
        refresh = mgr.create_refresh_token(user)
        new_access = mgr.refresh_access_token(refresh)
        assert new_access is not None

        data = mgr.verify_token(new_access)
        assert data is not None
        assert data.type == "access"

    def test_refresh_rejects_access_token(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user()
        access = mgr.create_access_token(user)
        assert mgr.refresh_access_token(access) is None


class TestAPIKey:
    """Tests for generate_api_key / verify_api_key."""

    def test_generate_and_verify_api_key(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user()
        key = mgr.generate_api_key(user, "test-key")
        data = mgr.verify_api_key(key)

        assert data is not None
        assert data.type == "api_key"
        assert data.user_id == user.id

    def test_verify_api_key_rejects_access_token(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user()
        access = mgr.create_access_token(user)
        assert mgr.verify_api_key(access) is None

    def test_verify_api_key_invalid(self, auth_config):
        mgr = AuthManager(auth_config)
        assert mgr.verify_api_key("invalid") is None


class TestResetToken:
    """Tests for create_reset_token / verify_reset_token."""

    def test_create_and_verify_reset_token(self, auth_config):
        mgr = AuthManager(auth_config)
        token = mgr.create_reset_token("user@test.com", "user-42")
        result = mgr.verify_reset_token(token)

        assert result is not None
        assert result["user_id"] == "user-42"
        assert result["email"] == "user@test.com"

    def test_reset_token_expired(self, auth_config):
        import jwt as pyjwt
        from datetime import datetime, timezone

        mgr = AuthManager(auth_config)
        payload = {
            "sub": "u1",
            "email": "e@e.com",
            "exp": datetime.now(timezone.utc) + timedelta(seconds=-1),
            "iat": datetime.now(timezone.utc),
            "type": "password_reset",
        }
        token = pyjwt.encode(payload, auth_config.jwt_secret, algorithm="HS256")
        assert mgr.verify_reset_token(token) is None

    def test_reset_token_wrong_type(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user()
        access = mgr.create_access_token(user)
        assert mgr.verify_reset_token(access) is None

    def test_reset_token_invalid(self, auth_config):
        mgr = AuthManager(auth_config)
        assert mgr.verify_reset_token("bad.token") is None


class TestCheckPermissions:
    """Tests for check_permissions."""

    def test_admin_has_all_permissions(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user(roles=[UserRole.ADMIN])
        token = mgr.create_access_token(user)
        data = mgr.verify_token(token)
        assert mgr.check_permissions(data, [UserRole.USER]) is True
        assert mgr.check_permissions(data, [UserRole.GUEST]) is True

    def test_user_has_user_permission(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user(roles=[UserRole.USER])
        token = mgr.create_access_token(user)
        data = mgr.verify_token(token)
        assert mgr.check_permissions(data, [UserRole.USER]) is True

    def test_guest_lacks_user_permission(self, auth_config, make_user):
        mgr = AuthManager(auth_config)
        user = make_user(roles=[UserRole.GUEST])
        token = mgr.create_access_token(user)
        data = mgr.verify_token(token)
        assert mgr.check_permissions(data, [UserRole.USER]) is False


class TestRBAC:
    """Tests for RoleBasedAccessControl."""

    def test_admin_hierarchy(self):
        roles = RoleBasedAccessControl.get_accessible_roles(UserRole.ADMIN)
        assert UserRole.ADMIN in roles
        assert UserRole.USER in roles
        assert UserRole.GUEST in roles
        assert UserRole.API in roles

    def test_user_hierarchy(self):
        roles = RoleBasedAccessControl.get_accessible_roles(UserRole.USER)
        assert UserRole.USER in roles
        assert UserRole.GUEST in roles
        assert UserRole.ADMIN not in roles

    def test_has_permission_admin(self):
        assert RoleBasedAccessControl.has_permission([UserRole.ADMIN], UserRole.USER) is True

    def test_has_permission_user_no_admin(self):
        assert RoleBasedAccessControl.has_permission([UserRole.USER], UserRole.ADMIN) is False

    def test_has_permission_guest(self):
        assert RoleBasedAccessControl.has_permission([UserRole.GUEST], UserRole.GUEST) is True
        assert RoleBasedAccessControl.has_permission([UserRole.GUEST], UserRole.USER) is False


class TestAuthManagerInit:
    """Tests for AuthManager initialization."""

    def test_missing_jwt_secret_raises(self):
        from src.ghost.config import AuthConfig

        config = AuthConfig(jwt_secret="")
        with pytest.raises(ValueError, match="JWT secret key not configured"):
            AuthManager(config)


class TestUserDataclass:
    """Tests for User dataclass."""

    def test_user_defaults(self):
        user = User(id="1", username="u", email="e@e.com", roles=[UserRole.USER])
        assert user.is_active is True
        assert user.metadata == {}
        assert user.created_at is not None

    def test_user_explicit_fields(self, make_user):
        user = make_user(id="x", username="alice", email="a@b.com", roles=[UserRole.ADMIN])
        assert user.id == "x"
        assert user.username == "alice"
