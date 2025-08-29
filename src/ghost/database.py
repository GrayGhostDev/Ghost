"""
Database Management Module

Provides database connection management, session handling, and common database operations.
Supports PostgreSQL, SQLite, and other SQLAlchemy-compatible databases.
"""

import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, AsyncGenerator, Generator, Dict, Any, List
from sqlalchemy import create_engine, MetaData, Table, text, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.pool import QueuePool
import redis
import pymongo
from .config import get_config, DatabaseConfig, RedisConfig
from .logging import get_logger, LoggerMixin


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


class DatabaseManager(LoggerMixin):
    """Manages database connections and operations."""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or get_config().database
        self.engine: Optional[Engine] = None
        self.async_engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[sessionmaker[Session]] = None
        self.async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._metadata = MetaData()
    
    def initialize(self) -> None:
        """Initialize database connections."""
        self.logger.info(f"Initializing database connection to {self.config.host}:{self.config.port}")
        
        # Create synchronous engine
        self.engine = create_engine(
            self.config.url,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            echo=self.config.echo,
            poolclass=QueuePool,
        )
        
        # Create session factory
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        
        # Create async engine for async operations
        async_url = self.config.url.replace("postgresql://", "postgresql+asyncpg://")
        if async_url != self.config.url:  # Only if it's PostgreSQL
            self.async_engine = create_async_engine(
                async_url,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                echo=self.config.echo,
            )
            
            self.async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                expire_on_commit=False,
            )
        
        self.logger.info("Database initialization completed")
    
    def create_tables(self) -> None:
        """Create all tables defined in Base metadata."""
        if self.engine is None:
            self.initialize()
        
        if self.engine is not None:
            self.logger.info("Creating database tables")
            Base.metadata.create_all(bind=self.engine)
            self.logger.info("Database tables created successfully")
    
    async def create_tables_async(self) -> None:
        """Create all tables asynchronously."""
        if self.async_engine is None:
            raise RuntimeError("Async engine not available")
        
        self.logger.info("Creating database tables asynchronously")
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.logger.info("Database tables created successfully")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        if self.session_factory is None:
            self.initialize()
        
        if self.session_factory is None:
            raise RuntimeError("Session factory not initialized")
        
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session with automatic cleanup."""
        if self.async_session_factory is None:
            raise RuntimeError("Async session factory not available")
        
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Async database session error: {e}")
                raise
    
    def execute_raw_sql(self, sql: str, params: Optional[Dict] = None) -> Any:
        """Execute raw SQL query."""
        with self.get_session() as session:
            result = session.execute(text(sql), params or {})
            return result.fetchall()
    
    async def execute_raw_sql_async(self, sql: str, params: Optional[Dict] = None) -> Any:
        """Execute raw SQL query asynchronously."""
        async with self.get_async_session() as session:
            result = await session.execute(text(sql), params or {})
            return result.fetchall()
    
    def health_check(self) -> bool:
        """Check database connection health."""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False
    
    async def health_check_async(self) -> bool:
        """Check database connection health asynchronously."""
        try:
            async with self.get_async_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            self.logger.error(f"Async database health check failed: {e}")
            return False
    
    def close(self) -> None:
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
            self.logger.info("Database engine disposed")
        
        if self.async_engine:
            # Use dispose method for async engine
            asyncio.create_task(self.async_engine.dispose())
            self.logger.info("Async database engine closed")


class RedisManager(LoggerMixin):
    """Manages Redis connections and operations."""
    
    def __init__(self, config: Optional[RedisConfig] = None):
        self.config = config or get_config().redis
        self.client: Optional[redis.Redis] = None
        self.pool: Optional[redis.ConnectionPool] = None
    
    def initialize(self) -> None:
        """Initialize Redis connection."""
        self.logger.info(f"Initializing Redis connection to {self.config.host}:{self.config.port}")
        
        self.pool = redis.ConnectionPool(
            host=self.config.host,
            port=self.config.port,
            db=self.config.db,
            password=self.config.password if self.config.password else None,
            decode_responses=self.config.decode_responses,
        )
        
        self.client = redis.Redis(connection_pool=self.pool)
        self.logger.info("Redis initialization completed")
    
    def get_client(self) -> redis.Redis:
        """Get Redis client instance."""
        if self.client is None:
            self.initialize()
        if self.client is None:
            raise RuntimeError("Redis client not initialized")
        return self.client
    
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set a key-value pair in Redis."""
        client = self.get_client()
        result = client.set(key, value, ex=expire)
        return bool(result)
    
    def get(self, key: str) -> Any:
        """Get value by key from Redis."""
        client = self.get_client()
        return client.get(key)
    
    def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        client = self.get_client()
        return bool(client.delete(key))
    
    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        client = self.get_client()
        return bool(client.exists(key))
    
    def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            client = self.get_client()
            client.ping()
            return True
        except Exception as e:
            self.logger.error(f"Redis health check failed: {e}")
            return False
    
    def close(self) -> None:
        """Close Redis connections."""
        if self.client:
            self.client.close()
            self.logger.info("Redis client closed")


class MongoManager(LoggerMixin):
    """Manages MongoDB connections and operations."""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.client: Optional[pymongo.MongoClient] = None
        self.database: Optional[Any] = None
    
    def initialize(self, database_name: str) -> None:
        """Initialize MongoDB connection."""
        self.logger.info(f"Initializing MongoDB connection")
        
        self.client = pymongo.MongoClient(self.connection_string)
        self.database = self.client[database_name]
        
        self.logger.info("MongoDB initialization completed")
    
    def get_collection(self, collection_name: str):
        """Get a MongoDB collection."""
        if self.database is None:
            raise RuntimeError("MongoDB not initialized")
        return self.database[collection_name]
    
    def health_check(self) -> bool:
        """Check MongoDB connection health."""
        try:
            if self.client is None:
                return False
            self.client.admin.command('ping')
            return True
        except Exception as e:
            self.logger.error(f"MongoDB health check failed: {e}")
            return False
    
    def close(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.logger.info("MongoDB client closed")


# Global database managers
_db_manager: Optional[DatabaseManager] = None
_redis_manager: Optional[RedisManager] = None
_mongo_manager: Optional[MongoManager] = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_redis_manager() -> RedisManager:
    """Get the global Redis manager instance."""
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager


def get_mongo_manager(connection_string: Optional[str] = None) -> MongoManager:
    """Get the global MongoDB manager instance."""
    global _mongo_manager
    if _mongo_manager is None:
        if connection_string is None:
            raise ValueError("MongoDB connection string required")
        _mongo_manager = MongoManager(connection_string)
    return _mongo_manager


# Convenience functions
def get_db_session():
    """Get a database session."""
    return get_db_manager().get_session()


def get_async_db_session():
    """Get an async database session."""
    return get_db_manager().get_async_session()


def get_redis_client():
    """Get Redis client."""
    return get_redis_manager().get_client()
