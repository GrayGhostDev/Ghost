"""Tests for src/ghost/models.py — Repository pattern, User, Role, Permission, RBAC."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.ghost.database import Base
from src.ghost.models import (
    AuditMixin,
    BaseRepository,
    Permission,
    Role,
    RoleRepository,
    SoftDeleteMixin,
    TimestampMixin,
    User,
    UserRepository,
    UserSession,
    role_permissions,
    user_roles,
)


# ──────────────────────────────────────────────
# Fixtures — in-memory SQLite
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    """Create an in-memory SQLite engine with all tables."""
    # SQLite doesn't support UUID natively; SQLAlchemy handles it as CHAR(32)
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """Provide a transactional session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    sess = Session(bind=connection)
    yield sess
    sess.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def user_repo(session):
    return UserRepository(session)


@pytest.fixture
def role_repo(session):
    return RoleRepository(session)


def _make_user(session, username="testuser", email="test@example.com", password="Secret123!"):
    """Helper to create and persist a User."""
    user = User(
        id=uuid.uuid4(),
        username=username,
        email=email,
        password_hash="placeholder",
    )
    user.set_password(password)
    session.add(user)
    session.flush()
    return user


def _make_role(session, name="testrole", description="A test role"):
    role = Role(id=uuid.uuid4(), name=name, description=description)
    session.add(role)
    session.flush()
    return role


# ──────────────────────────────────────────────
# User model
# ──────────────────────────────────────────────

class TestUserModel:
    def test_set_and_verify_password(self, session):
        user = _make_user(session)
        assert user.verify_password("Secret123!")
        assert not user.verify_password("wrong")

    def test_full_name_with_names(self, session):
        user = _make_user(session)
        user.first_name = "John"
        user.last_name = "Doe"
        assert user.full_name == "John Doe"

    def test_full_name_fallback(self, session):
        user = _make_user(session)
        user.display_name = "JD"
        assert user.full_name == "JD"

    def test_full_name_username_fallback(self, session):
        user = _make_user(session)
        assert user.full_name == "testuser"

    def test_is_locked_false_by_default(self, session):
        user = _make_user(session)
        assert not user.is_locked

    def test_is_locked_when_locked_until_future(self, session):
        user = _make_user(session)
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        assert user.is_locked

    def test_is_locked_when_locked_until_past(self, session):
        user = _make_user(session)
        user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert not user.is_locked

    def test_to_dict(self, session):
        user = _make_user(session)
        d = user.to_dict()
        assert d["username"] == "testuser"
        assert d["email"] == "test@example.com"
        assert isinstance(d["id"], str)
        assert d["is_active"] is True


# ──────────────────────────────────────────────
# SoftDeleteMixin
# ──────────────────────────────────────────────

class TestSoftDelete:
    def test_soft_delete(self, session):
        user = _make_user(session)
        assert not user.is_deleted
        user.soft_delete()
        assert user.is_deleted
        assert user.deleted_at is not None

    def test_restore(self, session):
        user = _make_user(session)
        user.soft_delete()
        user.restore()
        assert not user.is_deleted
        assert user.deleted_at is None


# ──────────────────────────────────────────────
# AuditMixin
# ──────────────────────────────────────────────

class TestAuditMixin:
    def test_add_audit_entry(self, session):
        user = _make_user(session)
        initial_version = user.version
        user.add_audit_entry("created", user="admin", details={"source": "test"})
        assert len(user.audit_log) == 1
        assert user.audit_log[0]["action"] == "created"
        assert user.version == initial_version + 1
        assert user.updated_by == "admin"

    def test_multiple_audit_entries(self, session):
        user = _make_user(session)
        user.add_audit_entry("created", user="admin")
        user.add_audit_entry("updated", user="admin", details={"field": "email"})
        assert len(user.audit_log) == 2


# ──────────────────────────────────────────────
# Role & Permission models
# ──────────────────────────────────────────────

class TestRoleModel:
    def test_role_to_dict(self, session):
        role = _make_role(session)
        d = role.to_dict()
        assert d["name"] == "testrole"
        assert isinstance(d["permissions"], list)

    def test_user_has_role(self, session):
        user = _make_user(session)
        role = _make_role(session, name="admin")
        user.roles.append(role)
        session.flush()
        assert user.has_role("admin")
        assert not user.has_role("nonexistent")


class TestPermissionModel:
    def test_permission_to_dict(self, session):
        perm = Permission(
            id=uuid.uuid4(), name="users:read", resource="users", action="read",
            description="Read users",
        )
        session.add(perm)
        session.flush()
        d = perm.to_dict()
        assert d["name"] == "users:read"
        assert d["resource"] == "users"

    def test_user_has_permission(self, session):
        user = _make_user(session, username="permuser", email="perm@test.com")
        role = _make_role(session, name="editor")
        perm = Permission(
            id=uuid.uuid4(), name="posts:write", resource="posts", action="write",
        )
        session.add(perm)
        session.flush()
        role.permissions.append(perm)
        user.roles.append(role)
        session.flush()
        assert user.has_permission("posts:write")
        assert not user.has_permission("posts:delete")


# ──────────────────────────────────────────────
# UserSession
# ──────────────────────────────────────────────

class TestUserSession:
    def test_is_expired(self, session):
        user = _make_user(session, username="sessuser", email="sess@test.com")
        sess_obj = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token="tok-1",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        session.add(sess_obj)
        session.flush()
        assert sess_obj.is_expired

    def test_is_valid(self, session):
        user = _make_user(session, username="valuser", email="val@test.com")
        sess_obj = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token="tok-valid",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(sess_obj)
        session.flush()
        assert sess_obj.is_valid

    def test_revoke(self, session):
        user = _make_user(session, username="revuser", email="rev@test.com")
        sess_obj = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token="tok-rev",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(sess_obj)
        session.flush()
        sess_obj.revoke(reason="logout")
        assert not sess_obj.is_active
        assert sess_obj.revoked_at is not None
        assert sess_obj.revoked_reason == "logout"
        assert not sess_obj.is_valid


# ──────────────────────────────────────────────
# BaseRepository (via UserRepository)
# ──────────────────────────────────────────────

class TestBaseRepository:
    def test_create_and_get(self, user_repo, session):
        user = user_repo.create(
            id=uuid.uuid4(),
            username="repo_user",
            email="repo@test.com",
            password_hash="x",
        )
        assert user.id is not None
        found = user_repo.get(user.id)
        assert found is not None
        assert found.username == "repo_user"

    def test_get_by(self, user_repo, session):
        user_repo.create(
            id=uuid.uuid4(),
            username="getby_user",
            email="getby@test.com",
            password_hash="x",
        )
        found = user_repo.get_by(username="getby_user")
        assert found is not None
        assert found.email == "getby@test.com"

    def test_get_all(self, user_repo, session):
        for i in range(3):
            user_repo.create(
                id=uuid.uuid4(),
                username=f"list_user_{i}",
                email=f"list{i}@test.com",
                password_hash="x",
            )
        results = user_repo.get_all()
        assert len(results) >= 3

    def test_count(self, user_repo, session):
        for i in range(2):
            user_repo.create(
                id=uuid.uuid4(),
                username=f"count_user_{i}",
                email=f"count{i}@test.com",
                password_hash="x",
            )
        c = user_repo.count()
        assert c >= 2

    def test_update(self, user_repo, session):
        user = user_repo.create(
            id=uuid.uuid4(),
            username="upd_user",
            email="upd@test.com",
            password_hash="x",
        )
        updated = user_repo.update(user.id, first_name="Updated")
        assert updated is not None
        assert updated.first_name == "Updated"

    def test_update_nonexistent(self, user_repo):
        result = user_repo.update(uuid.uuid4(), first_name="Nope")
        assert result is None

    def test_soft_delete(self, user_repo, session):
        user = user_repo.create(
            id=uuid.uuid4(),
            username="del_user",
            email="del@test.com",
            password_hash="x",
        )
        assert user_repo.delete(user.id, soft=True)
        # Soft-deleted users are excluded from get_all
        all_users = user_repo.get_all()
        assert all(u.username != "del_user" for u in all_users)

    def test_hard_delete(self, user_repo, session):
        user = user_repo.create(
            id=uuid.uuid4(),
            username="hard_del",
            email="harddel@test.com",
            password_hash="x",
        )
        uid = user.id
        assert user_repo.delete(uid, soft=False)
        assert user_repo.get(uid) is None

    def test_delete_nonexistent(self, user_repo):
        assert not user_repo.delete(uuid.uuid4())

    def test_bulk_create(self, user_repo, session):
        entities = [
            {"id": uuid.uuid4(), "username": f"bulk_{i}", "email": f"bulk{i}@test.com", "password_hash": "x"}
            for i in range(3)
        ]
        results = user_repo.bulk_create(entities)
        assert len(results) == 3


# ──────────────────────────────────────────────
# UserRepository specific methods
# ──────────────────────────────────────────────

class TestUserRepository:
    def test_get_by_username(self, user_repo, session):
        _make_user(session, username="findme", email="findme@test.com")
        found = user_repo.get_by_username("findme")
        assert found is not None
        assert found.email == "findme@test.com"

    def test_get_by_email(self, user_repo, session):
        _make_user(session, username="emailuser", email="specific@test.com")
        found = user_repo.get_by_email("specific@test.com")
        assert found is not None

    def test_authenticate_success(self, user_repo, session):
        _make_user(session, username="authuser", email="auth@test.com", password="Pass1234!")
        user = user_repo.authenticate("authuser", "Pass1234!")
        assert user is not None
        assert user.login_count == 1
        assert user.failed_login_count == 0

    def test_authenticate_by_email(self, user_repo, session):
        _make_user(session, username="emailauth", email="emailauth@test.com", password="Pass1234!")
        user = user_repo.authenticate("emailauth@test.com", "Pass1234!")
        assert user is not None

    def test_authenticate_wrong_password(self, user_repo, session):
        _make_user(session, username="wrongpw", email="wrongpw@test.com", password="Pass1234!")
        user = user_repo.authenticate("wrongpw", "WrongPass!")
        assert user is None

    def test_authenticate_locks_after_failures(self, user_repo, session):
        _make_user(session, username="lockme", email="lockme@test.com", password="Pass1234!")
        for _ in range(5):
            user_repo.authenticate("lockme", "bad")
        user = user_repo.get_by_username("lockme")
        assert user is not None
        assert user.locked_until is not None
        assert user.failed_login_count >= 5

    def test_authenticate_nonexistent_user(self, user_repo):
        result = user_repo.authenticate("ghost", "nope")
        assert result is None


# ──────────────────────────────────────────────
# RoleRepository
# ──────────────────────────────────────────────

class TestRoleRepository:
    def test_get_by_name(self, role_repo, session):
        _make_role(session, name="findable")
        found = role_repo.get_by_name("findable")
        assert found is not None
        assert found.name == "findable"

    def test_get_by_name_missing(self, role_repo):
        assert role_repo.get_by_name("nonexistent") is None
