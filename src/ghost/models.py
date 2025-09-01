"""
Database Models and Repository Pattern Module

Provides base models, mixins, and repository pattern for database operations.
Includes common models like User, Role, and audit tracking.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Type, TypeVar, Generic, Union
from enum import Enum
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, ForeignKey, Table, Index, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Session, declarative_mixin, declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
import bcrypt
from .database import Base
from .logging import get_logger, LoggerMixin


T = TypeVar('T', bound=Base)


# Mixins
@declarative_mixin
class TimestampMixin:
    """Mixin for automatic timestamp tracking."""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    @declared_attr
    def updated_at(cls):
        return Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), 
                     onupdate=lambda: datetime.now(timezone.utc), nullable=False)


@declarative_mixin
class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    
    @declared_attr
    def deleted_at(cls):
        return Column(DateTime(timezone=True), nullable=True)
    
    @declared_attr
    def is_deleted(cls):
        return Column(Boolean, default=False, nullable=False, index=True)
    
    def soft_delete(self):
        """Mark record as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
    
    def restore(self):
        """Restore soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None


@declarative_mixin
class AuditMixin:
    """Mixin for audit tracking."""
    
    @declared_attr
    def created_by(cls):
        return Column(String(255), nullable=True)
    
    @declared_attr
    def updated_by(cls):
        return Column(String(255), nullable=True)
    
    @declared_attr
    def version(cls):
        return Column(Integer, default=1, nullable=False)
    
    @declared_attr
    def audit_log(cls):
        return Column(JSON, default=list, nullable=False)
    
    def add_audit_entry(self, action: str, user: Optional[str] = None, details: Optional[Dict] = None):
        """Add an audit log entry."""
        if self.audit_log is None:
            self.audit_log = []
        
        entry = {
            'action': action,
            'user': user,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'version': self.version,
            'details': details or {}
        }
        
        self.audit_log = self.audit_log + [entry]  # Create new list for SQLAlchemy to detect change
        self.version += 1
        
        if user:
            self.updated_by = user


# Association tables
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE')),
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'))
)

role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE')),
    Column('permission_id', UUID(as_uuid=True), ForeignKey('permissions.id', ondelete='CASCADE'))
)


# Models
class User(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """User model with authentication and authorization."""
    
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Profile fields
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    display_name = Column(String(200), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    
    # Status fields
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    
    # Auth fields
    last_login = Column(DateTime(timezone=True), nullable=True)
    login_count = Column(Integer, default=0, nullable=False)
    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    # 2FA fields
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(255), nullable=True)
    
    # Additional data
    settings = Column(JSON, default=dict, nullable=False)
    metadata = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    roles = relationship('Role', secondary=user_roles, back_populates='users', lazy='selectin')
    sessions = relationship('UserSession', back_populates='user', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        Index('ix_users_email_active', 'email', 'is_active'),
        Index('ix_users_username_active', 'username', 'is_active'),
    )
    
    def set_password(self, password: str):
        """Hash and set password."""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    @hybrid_property
    def full_name(self) -> str:
        """Get full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.display_name or self.username
    
    @property
    def is_locked(self) -> bool:
        """Check if account is locked."""
        if self.locked_until:
            return datetime.now(timezone.utc) < self.locked_until
        return False
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return any(role.name == role_name for role in self.roles)
    
    def has_permission(self, permission_name: str) -> bool:
        """Check if user has a specific permission."""
        for role in self.roles:
            for permission in role.permissions:
                if permission.name == permission_name:
                    return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'display_name': self.display_name,
            'full_name': self.full_name,
            'avatar_url': self.avatar_url,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'is_superuser': self.is_superuser,
            'roles': [role.name for role in self.roles],
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class Role(Base, TimestampMixin, AuditMixin):
    """Role model for RBAC."""
    
    __tablename__ = 'roles'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    
    # Relationships
    users = relationship('User', secondary=user_roles, back_populates='roles')
    permissions = relationship('Permission', secondary=role_permissions, back_populates='roles', lazy='selectin')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'is_system': self.is_system,
            'priority': self.priority,
            'permissions': [perm.name for perm in self.permissions],
            'created_at': self.created_at.isoformat()
        }


class Permission(Base, TimestampMixin):
    """Permission model for fine-grained access control."""
    
    __tablename__ = 'permissions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    resource = Column(String(100), nullable=False, index=True)
    action = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    
    # Relationships
    roles = relationship('Role', secondary=role_permissions, back_populates='permissions')
    
    # Unique constraint on resource + action
    __table_args__ = (
        Index('ix_permissions_resource_action', 'resource', 'action', unique=True),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'name': self.name,
            'resource': self.resource,
            'action': self.action,
            'description': self.description
        }


class UserSession(Base, TimestampMixin):
    """User session tracking."""
    
    __tablename__ = 'user_sessions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = Column(String(500), unique=True, nullable=False, index=True)
    refresh_token = Column(String(500), unique=True, nullable=True, index=True)
    
    # Session info
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_id = Column(String(255), nullable=True)
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=False)
    refresh_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_reason = Column(String(255), nullable=True)
    
    # Relationships
    user = relationship('User', back_populates='sessions')
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if session is valid."""
        return self.is_active and not self.is_expired and not self.revoked_at
    
    def revoke(self, reason: Optional[str] = None):
        """Revoke session."""
        self.is_active = False
        self.revoked_at = datetime.now(timezone.utc)
        self.revoked_reason = reason


# Repository Pattern
class BaseRepository(Generic[T], LoggerMixin):
    """Base repository for database operations."""
    
    def __init__(self, model: Type[T], session: Union[Session, AsyncSession]):
        """Initialize repository.
        
        Args:
            model: Model class
            session: Database session
        """
        self.model = model
        self.session = session
        self._is_async = isinstance(session, AsyncSession)
    
    def _apply_filters(self, query, filters: Optional[Dict[str, Any]] = None):
        """Apply filters to query.
        
        Args:
            query: SQLAlchemy query
            filters: Filter conditions
            
        Returns:
            Filtered query
        """
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if isinstance(value, list):
                        query = query.filter(getattr(self.model, key).in_(value))
                    elif value is None:
                        query = query.filter(getattr(self.model, key).is_(None))
                    else:
                        query = query.filter(getattr(self.model, key) == value)
        return query
    
    async def get_async(self, id: Any) -> Optional[T]:
        """Get entity by ID (async).
        
        Args:
            id: Entity ID
            
        Returns:
            Entity or None
        """
        if not self._is_async:
            raise RuntimeError("Async session required for async operations")
        
        result = await self.session.execute(
            select(self.model).filter(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    def get(self, id: Any) -> Optional[T]:
        """Get entity by ID.
        
        Args:
            id: Entity ID
            
        Returns:
            Entity or None
        """
        if self._is_async:
            raise RuntimeError("Sync session required for sync operations")
        
        return self.session.query(self.model).filter(self.model.id == id).first()
    
    async def get_by_async(self, **kwargs) -> Optional[T]:
        """Get entity by field values (async).
        
        Args:
            **kwargs: Field conditions
            
        Returns:
            Entity or None
        """
        if not self._is_async:
            raise RuntimeError("Async session required for async operations")
        
        query = select(self.model)
        query = self._apply_filters(query, kwargs)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    def get_by(self, **kwargs) -> Optional[T]:
        """Get entity by field values.
        
        Args:
            **kwargs: Field conditions
            
        Returns:
            Entity or None
        """
        if self._is_async:
            raise RuntimeError("Sync session required for sync operations")
        
        query = self.session.query(self.model)
        query = self._apply_filters(query, kwargs)
        return query.first()
    
    async def get_all_async(self, filters: Optional[Dict[str, Any]] = None,
                            skip: int = 0, limit: int = 100,
                            order_by: Optional[str] = None) -> List[T]:
        """Get all entities with pagination (async).
        
        Args:
            filters: Filter conditions
            skip: Number of records to skip
            limit: Maximum records to return
            order_by: Field to order by
            
        Returns:
            List of entities
        """
        if not self._is_async:
            raise RuntimeError("Async session required for async operations")
        
        query = select(self.model)
        query = self._apply_filters(query, filters)
        
        # Handle soft deletes
        if hasattr(self.model, 'is_deleted'):
            query = query.filter(self.model.is_deleted == False)
        
        # Order
        if order_by:
            if order_by.startswith('-'):
                query = query.order_by(getattr(self.model, order_by[1:]).desc())
            else:
                query = query.order_by(getattr(self.model, order_by))
        
        # Pagination
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    def get_all(self, filters: Optional[Dict[str, Any]] = None,
               skip: int = 0, limit: int = 100,
               order_by: Optional[str] = None) -> List[T]:
        """Get all entities with pagination.
        
        Args:
            filters: Filter conditions
            skip: Number of records to skip
            limit: Maximum records to return
            order_by: Field to order by
            
        Returns:
            List of entities
        """
        if self._is_async:
            raise RuntimeError("Sync session required for sync operations")
        
        query = self.session.query(self.model)
        query = self._apply_filters(query, filters)
        
        # Handle soft deletes
        if hasattr(self.model, 'is_deleted'):
            query = query.filter(self.model.is_deleted == False)
        
        # Order
        if order_by:
            if order_by.startswith('-'):
                query = query.order_by(getattr(self.model, order_by[1:]).desc())
            else:
                query = query.order_by(getattr(self.model, order_by))
        
        # Pagination
        return query.offset(skip).limit(limit).all()
    
    async def count_async(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities (async).
        
        Args:
            filters: Filter conditions
            
        Returns:
            Count of entities
        """
        if not self._is_async:
            raise RuntimeError("Async session required for async operations")
        
        query = select(func.count()).select_from(self.model)
        query = self._apply_filters(query, filters)
        
        # Handle soft deletes
        if hasattr(self.model, 'is_deleted'):
            query = query.filter(self.model.is_deleted == False)
        
        result = await self.session.execute(query)
        return result.scalar()
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities.
        
        Args:
            filters: Filter conditions
            
        Returns:
            Count of entities
        """
        if self._is_async:
            raise RuntimeError("Sync session required for sync operations")
        
        query = self.session.query(func.count(self.model.id))
        query = self._apply_filters(query, filters)
        
        # Handle soft deletes
        if hasattr(self.model, 'is_deleted'):
            query = query.filter(self.model.is_deleted == False)
        
        return query.scalar()
    
    async def create_async(self, **kwargs) -> T:
        """Create new entity (async).
        
        Args:
            **kwargs: Entity fields
            
        Returns:
            Created entity
        """
        if not self._is_async:
            raise RuntimeError("Async session required for async operations")
        
        entity = self.model(**kwargs)
        self.session.add(entity)
        await self.session.flush()
        return entity
    
    def create(self, **kwargs) -> T:
        """Create new entity.
        
        Args:
            **kwargs: Entity fields
            
        Returns:
            Created entity
        """
        if self._is_async:
            raise RuntimeError("Sync session required for sync operations")
        
        entity = self.model(**kwargs)
        self.session.add(entity)
        self.session.flush()
        return entity
    
    async def update_async(self, id: Any, **kwargs) -> Optional[T]:
        """Update entity (async).
        
        Args:
            id: Entity ID
            **kwargs: Fields to update
            
        Returns:
            Updated entity or None
        """
        if not self._is_async:
            raise RuntimeError("Async session required for async operations")
        
        entity = await self.get_async(id)
        if entity:
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            # Update version if has audit mixin
            if hasattr(entity, 'version'):
                entity.version += 1
            
            await self.session.flush()
        return entity
    
    def update(self, id: Any, **kwargs) -> Optional[T]:
        """Update entity.
        
        Args:
            id: Entity ID
            **kwargs: Fields to update
            
        Returns:
            Updated entity or None
        """
        if self._is_async:
            raise RuntimeError("Sync session required for sync operations")
        
        entity = self.get(id)
        if entity:
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            # Update version if has audit mixin
            if hasattr(entity, 'version'):
                entity.version += 1
            
            self.session.flush()
        return entity
    
    async def delete_async(self, id: Any, soft: bool = True) -> bool:
        """Delete entity (async).
        
        Args:
            id: Entity ID
            soft: Use soft delete if available
            
        Returns:
            True if deleted
        """
        if not self._is_async:
            raise RuntimeError("Async session required for async operations")
        
        entity = await self.get_async(id)
        if entity:
            if soft and hasattr(entity, 'soft_delete'):
                entity.soft_delete()
            else:
                await self.session.delete(entity)
            await self.session.flush()
            return True
        return False
    
    def delete(self, id: Any, soft: bool = True) -> bool:
        """Delete entity.
        
        Args:
            id: Entity ID
            soft: Use soft delete if available
            
        Returns:
            True if deleted
        """
        if self._is_async:
            raise RuntimeError("Sync session required for sync operations")
        
        entity = self.get(id)
        if entity:
            if soft and hasattr(entity, 'soft_delete'):
                entity.soft_delete()
            else:
                self.session.delete(entity)
            self.session.flush()
            return True
        return False
    
    async def bulk_create_async(self, entities: List[Dict[str, Any]]) -> List[T]:
        """Bulk create entities (async).
        
        Args:
            entities: List of entity data
            
        Returns:
            Created entities
        """
        if not self._is_async:
            raise RuntimeError("Async session required for async operations")
        
        objects = [self.model(**entity) for entity in entities]
        self.session.add_all(objects)
        await self.session.flush()
        return objects
    
    def bulk_create(self, entities: List[Dict[str, Any]]) -> List[T]:
        """Bulk create entities.
        
        Args:
            entities: List of entity data
            
        Returns:
            Created entities
        """
        if self._is_async:
            raise RuntimeError("Sync session required for sync operations")
        
        objects = [self.model(**entity) for entity in entities]
        self.session.add_all(objects)
        self.session.flush()
        return objects


# Specific repositories
class UserRepository(BaseRepository[User]):
    """Repository for User operations."""
    
    def __init__(self, session: Union[Session, AsyncSession]):
        super().__init__(User, session)
    
    async def get_by_username_async(self, username: str) -> Optional[User]:
        """Get user by username (async)."""
        return await self.get_by_async(username=username)
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self.get_by(username=username)
    
    async def get_by_email_async(self, email: str) -> Optional[User]:
        """Get user by email (async)."""
        return await self.get_by_async(email=email)
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.get_by(email=email)
    
    async def authenticate_async(self, username: str, password: str) -> Optional[User]:
        """Authenticate user (async)."""
        user = await self.get_by_username_async(username)
        if not user:
            user = await self.get_by_email_async(username)
        
        if user and user.verify_password(password):
            # Update login info
            user.last_login = datetime.now(timezone.utc)
            user.login_count += 1
            user.failed_login_count = 0
            await self.session.flush()
            return user
        elif user:
            # Track failed login
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                # Lock account for 30 minutes
                user.locked_until = datetime.now(timezone.utc).replace(minute=30)
            await self.session.flush()
        
        return None
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user."""
        user = self.get_by_username(username)
        if not user:
            user = self.get_by_email(username)
        
        if user and user.verify_password(password):
            # Update login info
            user.last_login = datetime.now(timezone.utc)
            user.login_count += 1
            user.failed_login_count = 0
            self.session.flush()
            return user
        elif user:
            # Track failed login
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                # Lock account for 30 minutes
                from datetime import timedelta
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            self.session.flush()
        
        return None


class RoleRepository(BaseRepository[Role]):
    """Repository for Role operations."""
    
    def __init__(self, session: Union[Session, AsyncSession]):
        super().__init__(Role, session)
    
    async def get_by_name_async(self, name: str) -> Optional[Role]:
        """Get role by name (async)."""
        return await self.get_by_async(name=name)
    
    def get_by_name(self, name: str) -> Optional[Role]:
        """Get role by name."""
        return self.get_by(name=name)