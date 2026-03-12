"""Tests for src/ghost/database.py

Covers DatabaseManager, RedisManager, MongoManager, and global singleton helpers.
All external I/O (PostgreSQL, Redis, MongoDB) is mocked — no real connections needed.
"""

import asyncio
import pytest
from unittest.mock import (
    MagicMock,
    AsyncMock,
    patch,
    PropertyMock,
    call,
)
from contextlib import contextmanager

from src.ghost.config import DatabaseConfig, RedisConfig
import src.ghost.database as db_mod
from src.ghost.database import (
    Base,
    DatabaseManager,
    RedisManager,
    MongoManager,
    get_db_manager,
    get_redis_manager,
    get_mongo_manager,
    get_db_session,
    get_async_db_session,
    get_redis_client,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_database_globals():
    """Reset all module-level singletons between tests."""
    orig_db = db_mod._db_manager
    orig_redis = db_mod._redis_manager
    orig_mongo = db_mod._mongo_manager

    yield

    db_mod._db_manager = orig_db
    db_mod._redis_manager = orig_redis
    db_mod._mongo_manager = orig_mongo


@pytest.fixture
def db_config():
    """A DatabaseConfig pointing at a fake PostgreSQL instance."""
    return DatabaseConfig(
        host="localhost",
        port=5433,
        name="ghost_test",
        user="testuser",
        password="testpass",
        driver="postgresql",
        pool_size=5,
        max_overflow=10,
        echo=False,
    )


@pytest.fixture
def sqlite_config():
    """A DatabaseConfig using SQLite (no async engine created)."""
    return DatabaseConfig(
        driver="sqlite",
        name="test.db",
    )


@pytest.fixture
def redis_config():
    """A RedisConfig for testing."""
    return RedisConfig(
        host="localhost",
        port=6380,
        db=0,
        password="",
        decode_responses=True,
    )


@pytest.fixture
def redis_config_with_password():
    """A RedisConfig that has a password set."""
    return RedisConfig(
        host="localhost",
        port=6380,
        db=1,
        password="secret",
        decode_responses=True,
    )


# ──────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────


class TestBase:
    """Verify the declarative Base is usable."""

    def test_base_has_metadata(self):
        assert hasattr(Base, "metadata")

    def test_base_is_declarative(self):
        from sqlalchemy.orm import DeclarativeBase

        assert issubclass(Base, DeclarativeBase)


# ──────────────────────────────────────────────
# DatabaseManager — initialization
# ──────────────────────────────────────────────


class TestDatabaseManagerInit:
    def test_constructor_accepts_config(self, db_config):
        mgr = DatabaseManager(config=db_config)
        assert mgr.config is db_config
        assert mgr.engine is None
        assert mgr.async_engine is None
        assert mgr.session_factory is None
        assert mgr.async_session_factory is None

    @patch("src.ghost.database.get_config")
    def test_constructor_falls_back_to_global_config(self, mock_get_config):
        mock_cfg = MagicMock()
        mock_cfg.database = MagicMock(spec=DatabaseConfig)
        mock_get_config.return_value = mock_cfg

        mgr = DatabaseManager()
        assert mgr.config is mock_cfg.database


class TestDatabaseManagerInitialize:
    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_initialize_postgresql(self, mock_ce, mock_cae, db_config):
        """PostgreSQL URL triggers both sync and async engine creation."""
        mock_engine = MagicMock()
        mock_async_engine = MagicMock()
        mock_ce.return_value = mock_engine
        mock_cae.return_value = mock_async_engine

        mgr = DatabaseManager(config=db_config)
        mgr.initialize()

        # Sync engine: url rewritten from postgresql:// -> postgresql+psycopg://
        sync_url = mock_ce.call_args[0][0]
        assert sync_url.startswith("postgresql+psycopg://")
        mock_ce.assert_called_once()

        # Async engine: url rewritten from postgresql:// -> postgresql+asyncpg://
        async_url = mock_cae.call_args[0][0]
        assert async_url.startswith("postgresql+asyncpg://")
        mock_cae.assert_called_once()

        assert mgr.engine is mock_engine
        assert mgr.async_engine is mock_async_engine
        assert mgr.session_factory is not None
        assert mgr.async_session_factory is not None

    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_initialize_sqlite_no_async_engine(self, mock_ce, mock_cae, sqlite_config):
        """SQLite URL does not contain 'postgresql://' so no async engine is created."""
        mock_engine = MagicMock()
        mock_ce.return_value = mock_engine

        mgr = DatabaseManager(config=sqlite_config)
        mgr.initialize()

        mock_ce.assert_called_once()
        mock_cae.assert_not_called()
        assert mgr.async_engine is None
        assert mgr.async_session_factory is None

    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_initialize_pool_settings_forwarded(self, mock_ce, mock_cae, db_config):
        """Pool size, max_overflow, echo are forwarded to engine constructors."""
        mock_ce.return_value = MagicMock()
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        mgr.initialize()

        ce_kwargs = mock_ce.call_args
        assert ce_kwargs.kwargs["pool_size"] == 5
        assert ce_kwargs.kwargs["max_overflow"] == 10
        assert ce_kwargs.kwargs["echo"] is False

    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_initialize_psycopg_url_rewrite(self, mock_ce, mock_cae, db_config):
        """URL starting with postgresql:// is rewritten to use psycopg driver (line 53)."""
        mock_ce.return_value = MagicMock()
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        mgr.initialize()

        sync_url = mock_ce.call_args[0][0]
        assert "postgresql+psycopg://" in sync_url
        assert "postgresql://" not in sync_url  # original prefix removed


# ──────────────────────────────────────────────
# DatabaseManager — create_tables
# ──────────────────────────────────────────────


class TestDatabaseManagerCreateTables:
    @patch("src.ghost.database.create_engine")
    def test_create_tables_with_existing_engine(self, mock_ce, db_config):
        mock_engine = MagicMock()
        mock_ce.return_value = mock_engine

        mgr = DatabaseManager(config=db_config)
        mgr.engine = mock_engine

        with patch.object(Base.metadata, "create_all") as mock_create:
            mgr.create_tables()
            mock_create.assert_called_once_with(bind=mock_engine)

    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_create_tables_auto_initializes(self, mock_ce, mock_cae, db_config):
        """When engine is None, create_tables calls initialize() first."""
        mock_engine = MagicMock()
        mock_ce.return_value = mock_engine
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        assert mgr.engine is None

        with patch.object(Base.metadata, "create_all"):
            mgr.create_tables()

        # initialize() was called (engine was set)
        assert mgr.engine is not None


# ──────────────────────────────────────────────
# DatabaseManager — create_tables_async
# ──────────────────────────────────────────────


class TestDatabaseManagerCreateTablesAsync:
    @pytest.mark.asyncio
    async def test_create_tables_async_success(self, db_config):
        mgr = DatabaseManager(config=db_config)

        mock_conn = AsyncMock()
        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_begin.__aexit__ = AsyncMock(return_value=False)

        mock_async_engine = MagicMock()
        mock_async_engine.begin = MagicMock(return_value=mock_begin)
        mgr.async_engine = mock_async_engine

        await mgr.create_tables_async()
        mock_conn.run_sync.assert_awaited_once_with(Base.metadata.create_all)

    @pytest.mark.asyncio
    async def test_create_tables_async_raises_without_engine(self, db_config):
        mgr = DatabaseManager(config=db_config)
        assert mgr.async_engine is None

        with pytest.raises(RuntimeError, match="Async engine not available"):
            await mgr.create_tables_async()


# ──────────────────────────────────────────────
# DatabaseManager — get_session (sync context manager)
# ──────────────────────────────────────────────


class TestDatabaseManagerGetSession:
    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_get_session_yields_and_commits(self, mock_ce, mock_cae, db_config):
        mock_engine = MagicMock()
        mock_ce.return_value = mock_engine
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        mgr.initialize()

        mock_session = MagicMock()
        mgr.session_factory = MagicMock(return_value=mock_session)

        with mgr.get_session() as session:
            assert session is mock_session

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()

    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_get_session_rolls_back_on_error(self, mock_ce, mock_cae, db_config):
        mock_ce.return_value = MagicMock()
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        mgr.initialize()

        mock_session = MagicMock()
        mock_session.commit.side_effect = ValueError("commit failed")
        mgr.session_factory = MagicMock(return_value=mock_session)

        with pytest.raises(ValueError, match="commit failed"):
            with mgr.get_session() as session:
                pass  # commit is called on exit, which raises

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_get_session_rolls_back_on_user_exception(self, mock_ce, mock_cae, db_config):
        """Exception raised inside the with-block triggers rollback."""
        mock_ce.return_value = MagicMock()
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        mgr.initialize()

        mock_session = MagicMock()
        mgr.session_factory = MagicMock(return_value=mock_session)

        with pytest.raises(RuntimeError, match="user error"):
            with mgr.get_session() as session:
                raise RuntimeError("user error")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        # commit should not have been called since exception was raised before yield returned
        mock_session.commit.assert_not_called()

    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_get_session_auto_initializes(self, mock_ce, mock_cae, db_config):
        """If session_factory is None, get_session calls initialize()."""
        mock_engine = MagicMock()
        mock_ce.return_value = mock_engine
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        assert mgr.session_factory is None

        # After initialize, session_factory will be set — mock it to avoid real sessions
        original_init = mgr.initialize

        def patched_init():
            original_init()
            mgr.session_factory = MagicMock(return_value=MagicMock())

        with patch.object(mgr, "initialize", side_effect=patched_init):
            with mgr.get_session() as session:
                pass

    def test_get_session_raises_if_factory_still_none(self, db_config):
        """If initialize() fails to set session_factory, RuntimeError is raised."""
        mgr = DatabaseManager(config=db_config)

        with patch.object(mgr, "initialize"):  # initialize does nothing
            with pytest.raises(RuntimeError, match="Session factory not initialized"):
                with mgr.get_session() as session:
                    pass


# ──────────────────────────────────────────────
# DatabaseManager — get_async_session
# ──────────────────────────────────────────────


class TestDatabaseManagerGetAsyncSession:
    @pytest.mark.asyncio
    async def test_get_async_session_raises_without_factory(self, db_config):
        mgr = DatabaseManager(config=db_config)
        assert mgr.async_session_factory is None

        with pytest.raises(RuntimeError, match="Async session factory not available"):
            async with mgr.get_async_session() as session:
                pass

    @pytest.mark.asyncio
    async def test_get_async_session_commits_on_success(self, db_config):
        mgr = DatabaseManager(config=db_config)

        mock_session = AsyncMock()

        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx

        mgr.async_session_factory = mock_factory

        async with mgr.get_async_session() as session:
            assert session is mock_session

        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_async_session_rolls_back_on_error(self, db_config):
        mgr = DatabaseManager(config=db_config)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock(side_effect=ValueError("async commit failed"))

        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx

        mgr.async_session_factory = mock_factory

        with pytest.raises(ValueError, match="async commit failed"):
            async with mgr.get_async_session() as session:
                pass

        mock_session.rollback.assert_awaited_once()


# ──────────────────────────────────────────────
# DatabaseManager — execute_raw_sql
# ──────────────────────────────────────────────


class TestDatabaseManagerExecuteRawSqlAsync:
    @pytest.mark.asyncio
    async def test_execute_raw_sql_async(self, db_config):
        mgr = DatabaseManager(config=db_config)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("async_row",)]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx
        mgr.async_session_factory = mock_factory

        result = await mgr.execute_raw_sql_async("SELECT 1")
        assert result == [("async_row",)]
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_raw_sql_async_with_params(self, db_config):
        mgr = DatabaseManager(config=db_config)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("row",)]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx
        mgr.async_session_factory = mock_factory

        result = await mgr.execute_raw_sql_async(
            "SELECT * FROM t WHERE id = :id", {"id": 42}
        )
        assert result == [("row",)]


class TestDatabaseManagerExecuteRawSql:
    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_execute_raw_sql(self, mock_ce, mock_cae, db_config):
        mock_ce.return_value = MagicMock()
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        mgr.initialize()

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("row1",), ("row2",)]
        mock_session.execute.return_value = mock_result
        mgr.session_factory = MagicMock(return_value=mock_session)

        result = mgr.execute_raw_sql("SELECT * FROM users")
        assert result == [("row1",), ("row2",)]
        mock_session.execute.assert_called_once()

    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_execute_raw_sql_with_params(self, mock_ce, mock_cae, db_config):
        mock_ce.return_value = MagicMock()
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        mgr.initialize()

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("row1",)]
        mock_session.execute.return_value = mock_result
        mgr.session_factory = MagicMock(return_value=mock_session)

        result = mgr.execute_raw_sql("SELECT * FROM users WHERE id = :id", {"id": 1})
        assert result == [("row1",)]


# ──────────────────────────────────────────────
# DatabaseManager — health_check
# ──────────────────────────────────────────────


class TestDatabaseManagerHealthCheck:
    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_health_check_success(self, mock_ce, mock_cae, db_config):
        mock_ce.return_value = MagicMock()
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        mgr.initialize()

        mock_session = MagicMock()
        mgr.session_factory = MagicMock(return_value=mock_session)

        assert mgr.health_check() is True

    @patch("src.ghost.database.create_async_engine")
    @patch("src.ghost.database.create_engine")
    def test_health_check_failure(self, mock_ce, mock_cae, db_config):
        mock_ce.return_value = MagicMock()
        mock_cae.return_value = MagicMock()

        mgr = DatabaseManager(config=db_config)
        mgr.initialize()

        mock_session = MagicMock()
        mock_session.execute.side_effect = ConnectionError("db down")
        mgr.session_factory = MagicMock(return_value=mock_session)

        assert mgr.health_check() is False


# ──────────────────────────────────────────────
# DatabaseManager — health_check_async
# ──────────────────────────────────────────────


class TestDatabaseManagerHealthCheckAsync:
    @pytest.mark.asyncio
    async def test_health_check_async_success(self, db_config):
        mgr = DatabaseManager(config=db_config)

        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx
        mgr.async_session_factory = mock_factory

        assert await mgr.health_check_async() is True

    @pytest.mark.asyncio
    async def test_health_check_async_failure(self, db_config):
        mgr = DatabaseManager(config=db_config)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=ConnectionError("async db down"))
        mock_session.commit = AsyncMock()

        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx
        mgr.async_session_factory = mock_factory

        assert await mgr.health_check_async() is False


# ──────────────────────────────────────────────
# DatabaseManager — close
# ──────────────────────────────────────────────


class TestDatabaseManagerClose:
    def test_close_disposes_sync_engine(self, db_config):
        mgr = DatabaseManager(config=db_config)
        mock_engine = MagicMock()
        mgr.engine = mock_engine

        mgr.close()
        mock_engine.dispose.assert_called_once()

    def test_close_disposes_async_engine_no_loop(self, db_config):
        """When no running event loop, asyncio.run() is used to dispose."""
        mgr = DatabaseManager(config=db_config)
        mock_engine = MagicMock()
        mgr.engine = mock_engine

        mock_async_engine = MagicMock()
        mock_async_engine.dispose = AsyncMock()
        mgr.async_engine = mock_async_engine

        with patch("src.ghost.database.asyncio.get_running_loop", side_effect=RuntimeError):
            with patch("src.ghost.database.asyncio.run") as mock_run:
                mgr.close()

        mock_engine.dispose.assert_called_once()
        mock_run.assert_called_once()

    def test_close_disposes_async_engine_with_loop(self, db_config):
        """When an event loop is running, create_task is used."""
        mgr = DatabaseManager(config=db_config)
        mock_engine = MagicMock()
        mgr.engine = mock_engine

        mock_async_engine = MagicMock()
        mock_async_engine.dispose = AsyncMock()
        mgr.async_engine = mock_async_engine

        mock_loop = MagicMock()
        with patch("src.ghost.database.asyncio.get_running_loop", return_value=mock_loop):
            mgr.close()

        mock_engine.dispose.assert_called_once()
        mock_loop.create_task.assert_called_once()

    def test_close_no_engines(self, db_config):
        """Close with no engines does not raise."""
        mgr = DatabaseManager(config=db_config)
        mgr.close()  # Should not raise


# ──────────────────────────────────────────────
# RedisManager
# ──────────────────────────────────────────────


class TestRedisManagerInit:
    def test_constructor_accepts_config(self, redis_config):
        mgr = RedisManager(config=redis_config)
        assert mgr.config is redis_config
        assert mgr.client is None
        assert mgr.pool is None

    @patch("src.ghost.database.get_config")
    def test_constructor_falls_back_to_global_config(self, mock_get_config):
        mock_cfg = MagicMock()
        mock_cfg.redis = MagicMock(spec=RedisConfig)
        mock_get_config.return_value = mock_cfg

        mgr = RedisManager()
        assert mgr.config is mock_cfg.redis


class TestRedisManagerInitialize:
    @patch("src.ghost.database.redis.Redis")
    @patch("src.ghost.database.redis.ConnectionPool")
    def test_initialize_creates_pool_and_client(self, mock_pool_cls, mock_redis_cls, redis_config):
        mock_pool = MagicMock()
        mock_pool_cls.return_value = mock_pool
        mock_client = MagicMock()
        mock_redis_cls.return_value = mock_client

        mgr = RedisManager(config=redis_config)
        mgr.initialize()

        mock_pool_cls.assert_called_once_with(
            host="localhost",
            port=6380,
            db=0,
            password=None,  # empty string -> None
            decode_responses=True,
        )
        mock_redis_cls.assert_called_once_with(connection_pool=mock_pool)
        assert mgr.pool is mock_pool
        assert mgr.client is mock_client

    @patch("src.ghost.database.redis.Redis")
    @patch("src.ghost.database.redis.ConnectionPool")
    def test_initialize_with_password(self, mock_pool_cls, mock_redis_cls, redis_config_with_password):
        mock_pool_cls.return_value = MagicMock()
        mock_redis_cls.return_value = MagicMock()

        mgr = RedisManager(config=redis_config_with_password)
        mgr.initialize()

        pool_kwargs = mock_pool_cls.call_args
        assert pool_kwargs.kwargs["password"] == "secret"


class TestRedisManagerGetClient:
    def test_get_client_returns_existing(self, redis_config):
        mgr = RedisManager(config=redis_config)
        mock_client = MagicMock()
        mgr.client = mock_client

        assert mgr.get_client() is mock_client

    @patch("src.ghost.database.redis.Redis")
    @patch("src.ghost.database.redis.ConnectionPool")
    def test_get_client_auto_initializes(self, mock_pool_cls, mock_redis_cls, redis_config):
        mock_client = MagicMock()
        mock_pool_cls.return_value = MagicMock()
        mock_redis_cls.return_value = mock_client

        mgr = RedisManager(config=redis_config)
        assert mgr.client is None

        client = mgr.get_client()
        assert client is mock_client

    def test_get_client_raises_if_still_none(self, redis_config):
        """If initialize() fails to set client, RuntimeError is raised."""
        mgr = RedisManager(config=redis_config)

        with patch.object(mgr, "initialize"):  # initialize does nothing
            with pytest.raises(RuntimeError, match="Redis client not initialized"):
                mgr.get_client()


class TestRedisManagerOperations:
    @pytest.fixture
    def redis_mgr(self, redis_config):
        mgr = RedisManager(config=redis_config)
        mgr.client = MagicMock()
        return mgr

    def test_set_without_expire(self, redis_mgr):
        redis_mgr.client.set.return_value = True
        result = redis_mgr.set("key1", "value1")
        assert result is True
        redis_mgr.client.set.assert_called_once_with("key1", "value1", ex=None)

    def test_set_with_expire(self, redis_mgr):
        redis_mgr.client.set.return_value = True
        result = redis_mgr.set("key1", "value1", expire=300)
        assert result is True
        redis_mgr.client.set.assert_called_once_with("key1", "value1", ex=300)

    def test_get(self, redis_mgr):
        redis_mgr.client.get.return_value = "value1"
        result = redis_mgr.get("key1")
        assert result == "value1"
        redis_mgr.client.get.assert_called_once_with("key1")

    def test_get_missing_key(self, redis_mgr):
        redis_mgr.client.get.return_value = None
        result = redis_mgr.get("missing")
        assert result is None

    def test_delete(self, redis_mgr):
        redis_mgr.client.delete.return_value = 1
        result = redis_mgr.delete("key1")
        assert result is True
        redis_mgr.client.delete.assert_called_once_with("key1")

    def test_delete_missing_key(self, redis_mgr):
        redis_mgr.client.delete.return_value = 0
        result = redis_mgr.delete("missing")
        assert result is False

    def test_exists_true(self, redis_mgr):
        redis_mgr.client.exists.return_value = 1
        assert redis_mgr.exists("key1") is True

    def test_exists_false(self, redis_mgr):
        redis_mgr.client.exists.return_value = 0
        assert redis_mgr.exists("missing") is False


class TestRedisManagerHealthCheck:
    def test_health_check_success(self, redis_config):
        mgr = RedisManager(config=redis_config)
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mgr.client = mock_client

        assert mgr.health_check() is True
        mock_client.ping.assert_called_once()

    def test_health_check_failure(self, redis_config):
        mgr = RedisManager(config=redis_config)
        mock_client = MagicMock()
        mock_client.ping.side_effect = ConnectionError("redis down")
        mgr.client = mock_client

        assert mgr.health_check() is False


class TestRedisManagerClose:
    def test_close_with_client(self, redis_config):
        mgr = RedisManager(config=redis_config)
        mock_client = MagicMock()
        mgr.client = mock_client

        mgr.close()
        mock_client.close.assert_called_once()

    def test_close_without_client(self, redis_config):
        mgr = RedisManager(config=redis_config)
        mgr.close()  # Should not raise


# ──────────────────────────────────────────────
# MongoManager
# ──────────────────────────────────────────────


class TestMongoManagerInit:
    def test_constructor(self):
        mgr = MongoManager("mongodb://localhost:27017")
        assert mgr.connection_string == "mongodb://localhost:27017"
        assert mgr.client is None
        assert mgr.database is None


class TestMongoManagerInitialize:
    @patch("src.ghost.database.pymongo.MongoClient")
    def test_initialize(self, mock_mongo_cls):
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)
        mock_mongo_cls.return_value = mock_client

        mgr = MongoManager("mongodb://localhost:27017")
        mgr.initialize("test_db")

        mock_mongo_cls.assert_called_once_with("mongodb://localhost:27017")
        mock_client.__getitem__.assert_called_once_with("test_db")
        assert mgr.client is mock_client
        assert mgr.database is mock_db


class TestMongoManagerGetCollection:
    def test_get_collection_success(self):
        mgr = MongoManager("mongodb://localhost:27017")
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mgr.database = mock_db

        result = mgr.get_collection("users")
        assert result is mock_collection
        mock_db.__getitem__.assert_called_once_with("users")

    def test_get_collection_raises_without_init(self):
        mgr = MongoManager("mongodb://localhost:27017")
        with pytest.raises(RuntimeError, match="MongoDB not initialized"):
            mgr.get_collection("users")


class TestMongoManagerHealthCheck:
    def test_health_check_success(self):
        mgr = MongoManager("mongodb://localhost:27017")
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1.0}
        mgr.client = mock_client

        assert mgr.health_check() is True
        mock_client.admin.command.assert_called_once_with("ping")

    def test_health_check_failure_exception(self):
        mgr = MongoManager("mongodb://localhost:27017")
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = ConnectionError("mongo down")
        mgr.client = mock_client

        assert mgr.health_check() is False

    def test_health_check_no_client(self):
        mgr = MongoManager("mongodb://localhost:27017")
        assert mgr.client is None
        assert mgr.health_check() is False


class TestMongoManagerClose:
    def test_close_with_client(self):
        mgr = MongoManager("mongodb://localhost:27017")
        mock_client = MagicMock()
        mgr.client = mock_client

        mgr.close()
        mock_client.close.assert_called_once()

    def test_close_without_client(self):
        mgr = MongoManager("mongodb://localhost:27017")
        mgr.close()  # Should not raise


# ──────────────────────────────────────────────
# Global singleton helpers
# ──────────────────────────────────────────────


class TestGlobalGetters:
    @patch("src.ghost.database.get_config")
    def test_get_db_manager_creates_singleton(self, mock_get_config):
        mock_cfg = MagicMock()
        mock_cfg.database = DatabaseConfig()
        mock_get_config.return_value = mock_cfg

        db_mod._db_manager = None

        mgr1 = get_db_manager()
        mgr2 = get_db_manager()
        assert mgr1 is mgr2
        assert isinstance(mgr1, DatabaseManager)

    @patch("src.ghost.database.get_config")
    def test_get_redis_manager_creates_singleton(self, mock_get_config):
        mock_cfg = MagicMock()
        mock_cfg.redis = RedisConfig()
        mock_get_config.return_value = mock_cfg

        db_mod._redis_manager = None

        mgr1 = get_redis_manager()
        mgr2 = get_redis_manager()
        assert mgr1 is mgr2
        assert isinstance(mgr1, RedisManager)

    def test_get_mongo_manager_creates_singleton(self):
        db_mod._mongo_manager = None

        mgr1 = get_mongo_manager("mongodb://localhost:27017")
        mgr2 = get_mongo_manager()  # no conn string needed on second call
        assert mgr1 is mgr2
        assert isinstance(mgr1, MongoManager)

    def test_get_mongo_manager_raises_without_conn_string(self):
        db_mod._mongo_manager = None

        with pytest.raises(ValueError, match="MongoDB connection string required"):
            get_mongo_manager()

    @patch("src.ghost.database.get_config")
    def test_get_db_manager_returns_existing(self, mock_get_config):
        existing = MagicMock(spec=DatabaseManager)
        db_mod._db_manager = existing

        result = get_db_manager()
        assert result is existing
        mock_get_config.assert_not_called()

    @patch("src.ghost.database.get_config")
    def test_get_redis_manager_returns_existing(self, mock_get_config):
        existing = MagicMock(spec=RedisManager)
        db_mod._redis_manager = existing

        result = get_redis_manager()
        assert result is existing
        mock_get_config.assert_not_called()


class TestConvenienceFunctions:
    @patch("src.ghost.database.get_db_manager")
    def test_get_db_session(self, mock_get_mgr):
        mock_mgr = MagicMock()
        mock_get_mgr.return_value = mock_mgr

        result = get_db_session()
        mock_mgr.get_session.assert_called_once()
        assert result is mock_mgr.get_session.return_value

    @patch("src.ghost.database.get_db_manager")
    def test_get_async_db_session(self, mock_get_mgr):
        mock_mgr = MagicMock()
        mock_get_mgr.return_value = mock_mgr

        result = get_async_db_session()
        mock_mgr.get_async_session.assert_called_once()
        assert result is mock_mgr.get_async_session.return_value

    @patch("src.ghost.database.get_redis_manager")
    def test_get_redis_client(self, mock_get_mgr):
        mock_mgr = MagicMock()
        mock_get_mgr.return_value = mock_mgr

        result = get_redis_client()
        mock_mgr.get_client.assert_called_once()
        assert result is mock_mgr.get_client.return_value
