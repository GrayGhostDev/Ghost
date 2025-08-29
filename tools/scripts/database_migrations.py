#!/usr/bin/env python3
"""
Ghost Backend Framework - Database Migration System

Provides database migration, seeding, and schema management capabilities.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghost.database import get_db_manager
from ghost.config import get_config
from ghost.logging import get_logger

logger = get_logger("migrations")
Base = declarative_base()


class Migration(Base):
    """Migration tracking table."""
    __tablename__ = 'ghost_migrations'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    executed_at = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, default=True)


class User(Base):
    """User model for the backend."""
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserRole(Base):
    """User roles for authorization."""
    __tablename__ = 'user_roles'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    role = Column(String, nullable=False)  # admin, user, viewer, etc.
    frontend_type = Column(String, nullable=True)  # react, angular, vue, etc.
    created_at = Column(DateTime, default=datetime.utcnow)


class APIKey(Base):
    """API Key management."""
    __tablename__ = 'api_keys'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    key_hash = Column(String, unique=True, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=True)
    is_active = Column(Boolean, default=True)
    permissions = Column(String, nullable=True)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)


class MigrationRunner:
    """Handles database migrations and seeding."""
    
    def __init__(self):
        self.config = get_config()
        self.db_manager = get_db_manager()
        self.migrations_dir = Path(__file__).parent.parent.parent / "migrations"
        self.migrations_dir.mkdir(exist_ok=True)
        
    def init_migration_system(self):
        """Initialize the migration tracking system."""
        logger.info("Initializing migration system...")
        
        # Create migrations table
        engine = create_engine(self.config.database.url)
        Migration.__table__.create(engine, checkfirst=True)
        
        logger.info("✅ Migration system initialized")
    
    def create_all_tables(self):
        """Create all defined tables."""
        logger.info("Creating database tables...")
        
        engine = create_engine(self.config.database.url)
        Base.metadata.create_all(engine)
        
        logger.info("✅ All tables created")
    
    def run_migrations(self):
        """Run all pending migrations."""
        logger.info("Running database migrations...")
        
        self.init_migration_system()
        self.create_all_tables()
        
        # Mark initial migration as complete
        self._mark_migration_complete("001_initial_schema")
        
        logger.info("✅ Migrations completed")
    
    def seed_development_data(self):
        """Seed the database with development data."""
        logger.info("Seeding development data...")
        
        engine = create_engine(self.config.database.url)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            # Check if admin user exists
            admin_user = session.query(User).filter(User.username == "admin").first()
            
            if not admin_user:
                # Create admin user
                from ghost.auth import AuthManager
                auth_manager = AuthManager()
                
                admin_user = User(
                    username="admin",
                    email="admin@localhost",
                    password_hash=auth_manager.hash_password("admin123"),
                    is_active=True,
                    is_superuser=True
                )
                session.add(admin_user)
                session.flush()
                
                # Add admin role
                admin_role = UserRole(
                    user_id=admin_user.id,
                    role="admin"
                )
                session.add(admin_role)
                
                logger.info("✅ Admin user created (username: admin, password: admin123)")
            
            # Create test user
            test_user = session.query(User).filter(User.username == "testuser").first()
            if not test_user:
                from ghost.auth import AuthManager
                auth_manager = AuthManager()
                
                test_user = User(
                    username="testuser",
                    email="test@localhost",
                    password_hash=auth_manager.hash_password("test123"),
                    is_active=True,
                    is_superuser=False
                )
                session.add(test_user)
                session.flush()
                
                # Add user role
                user_role = UserRole(
                    user_id=test_user.id,
                    role="user"
                )
                session.add(user_role)
                
                logger.info("✅ Test user created (username: testuser, password: test123)")
            
            # Create API keys for frontend types
            frontend_types = ["react", "angular", "vue", "mobile"]
            
            for frontend_type in frontend_types:
                existing_key = session.query(APIKey).filter(
                    APIKey.name == f"{frontend_type}_dev_key"
                ).first()
                
                if not existing_key:
                    import secrets
                    key_value = secrets.token_urlsafe(32)
                    
                    api_key = APIKey(
                        name=f"{frontend_type}_dev_key",
                        key_hash=auth_manager.hash_password(key_value),
                        permissions='{"read": true, "write": true}',
                        is_active=True
                    )
                    session.add(api_key)
                    logger.info(f"✅ API key created for {frontend_type}: {key_value}")
            
            session.commit()
            logger.info("✅ Development data seeded")
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Error seeding data: {e}")
            raise
        finally:
            session.close()
    
    def _mark_migration_complete(self, migration_name: str):
        """Mark a migration as completed."""
        engine = create_engine(self.config.database.url)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            existing = session.query(Migration).filter(Migration.name == migration_name).first()
            if not existing:
                migration = Migration(name=migration_name)
                session.add(migration)
                session.commit()
        finally:
            session.close()
    
    def reset_database(self):
        """Reset the database (DROP and CREATE all tables)."""
        logger.warning("🗑️  Resetting database - ALL DATA WILL BE LOST!")
        
        engine = create_engine(self.config.database.url)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        
        logger.info("✅ Database reset completed")
    
    def get_migration_status(self) -> List[Dict[str, Any]]:
        """Get the status of all migrations."""
        engine = create_engine(self.config.database.url)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            migrations = session.query(Migration).order_by(Migration.executed_at).all()
            return [
                {
                    "name": m.name,
                    "executed_at": m.executed_at.isoformat(),
                    "success": m.success
                }
                for m in migrations
            ]
        finally:
            session.close()


def main():
    """Main function for running migrations."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Database Migration Tool')
    parser.add_argument('command', choices=[
        'migrate', 'seed', 'reset', 'status', 'create-tables'
    ])
    parser.add_argument('--force', action='store_true', help='Force operation')
    
    args = parser.parse_args()
    
    runner = MigrationRunner()
    
    try:
        if args.command == 'migrate':
            runner.run_migrations()
        
        elif args.command == 'seed':
            runner.seed_development_data()
        
        elif args.command == 'reset':
            if args.force:
                runner.reset_database()
            else:
                print("⚠️  Use --force to confirm database reset")
                
        elif args.command == 'status':
            status = runner.get_migration_status()
            print("\n📊 Migration Status:")
            for migration in status:
                print(f"  ✅ {migration['name']} - {migration['executed_at']}")
        
        elif args.command == 'create-tables':
            runner.create_all_tables()
        
        print("\n✅ Migration command completed!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
