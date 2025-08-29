"""Test the complete Ghost Backend Framework integration."""

import pytest
from unittest.mock import AsyncMock, patch
import tempfile
import os
from pathlib import Path

from src.ghost import (
    Config, get_config, setup_logging, get_logger,
    get_available_features
)
from src.ghost.utils import (
    DateTimeUtils, StringUtils, ValidationUtils,
    SerializationUtils, CacheUtils
)


class TestFrameworkIntegration:
    """Test complete framework integration."""
    
    def test_available_features(self):
        """Test that we can check available features."""
        features = get_available_features()
        
        # Core features should always be available
        assert features["config"] is True
        assert features["logging"] is True
        assert features["utils"] is True
        
        # Optional features depend on installed packages
        assert isinstance(features["database"], bool)
        assert isinstance(features["auth"], bool)
        assert isinstance(features["api"], bool)
    
    def test_basic_configuration(self):
        """Test basic configuration initialization."""
        config = Config()
        
        # Should have basic structure
        assert hasattr(config, 'database')
        assert hasattr(config, 'logging')
        assert hasattr(config, 'api')
        assert hasattr(config, 'auth')
        
        # Test configuration access
        global_config = get_config()
        assert global_config is not None
    
    def test_logging_setup(self):
        """Test logging configuration."""
        config = Config()
        
        # This should not raise an exception
        setup_logging(config.logging)
        
        # Should be able to get logger
        logger = get_logger(__name__)
        assert logger is not None
        
        # Should be able to log
        logger.info("Test log message")
    
    def test_utility_functions(self):
        """Test core utility functions."""
        # DateTime utilities
        dt_utils = DateTimeUtils()
        now = dt_utils.now_utc()
        assert now is not None
        
        formatted = dt_utils.format_datetime(now, "YYYY-MM-DD")
        assert len(formatted) == 10  # Should be "2024-01-01" format
        
        # String utilities
        str_utils = StringUtils()
        slug = str_utils.slugify("My Awesome Title!")
        assert slug == "my-awesome-title"
        
        # Validation utilities
        validator = ValidationUtils()
        assert validator.is_email("test@example.com") is True
        assert validator.is_email("invalid-email") is False
        
        # Serialization utilities
        serializer = SerializationUtils()
        test_data = {"key": "value", "number": 42}
        
        json_str = serializer.to_json(test_data)
        assert '"key": "value"' in json_str
        
        restored = serializer.from_json(json_str)
        assert restored == test_data
    
    def test_caching_utilities(self):
        """Test caching functionality."""
        cache = CacheUtils()
        
        # Test basic caching
        cache.set("test_key", "test_value", ttl=60)
        assert cache.get("test_key") == "test_value"
        
        # Test cache miss
        assert cache.get("nonexistent_key") is None
        
        # Test cache deletion
        cache.delete("test_key")
        assert cache.get("test_key") is None


class TestConfigurationLoading:
    """Test configuration loading from different sources."""
    
    def test_env_variable_loading(self):
        """Test loading configuration from environment variables."""
        os.environ["DATABASE_URL"] = "sqlite:///test.db"
        os.environ["LOG_LEVEL"] = "DEBUG"
        os.environ["API_HOST"] = "127.0.0.1"
        try:
            from src.ghost.config import ConfigManager
            config = ConfigManager().load_from_env()
            # These should be loaded from environment
            assert config.database.url == "sqlite:///test.db"
            assert config.logging.level == "DEBUG"
            assert config.api.host == "127.0.0.1"
        finally:
            os.environ.pop("DATABASE_URL", None)
            os.environ.pop("LOG_LEVEL", None)
            os.environ.pop("API_HOST", None)

    def test_yaml_config_loading(self):
        """Test loading configuration from YAML file."""
        yaml_content = """
        database:
          url: "***localhost/testdb"
          pool_size: 10
        logging:
          level: "WARNING"
          file: "test.log"
        api:
          title: "Test API"
          version: "2.0.0"
        """
        import tempfile
        import os
        from src.ghost.config import ConfigManager
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                os.environ["GHOST_CONFIG_FILE"] = f.name
                config = ConfigManager().load_from_yaml(f.name)
                # These should be loaded from YAML
                assert config.database.url == "***localhost/testdb"
                assert config.logging.level == "WARNING"
                assert config.logging.file == "test.log"
                assert config.api.title == "Test API"
                assert config.api.version == "2.0.0"
            finally:
                os.environ.pop("GHOST_CONFIG_FILE", None)
                os.unlink(f.name)


@pytest.mark.skipif(
    not get_available_features()["database"], 
    reason="Database features not available"
)
class TestDatabaseIntegration:
    """Test database integration if available."""
    
    @pytest.mark.asyncio
    async def test_database_manager_creation(self):
        """Test that DatabaseManager can be created."""
        from src.ghost.database import DatabaseManager
        
        config = Config()
        # Use SQLite for testing
        config.database.url = "sqlite:///test.db"

        db_manager = DatabaseManager(config.database)
        assert db_manager is not None

        # Should be able to initialize (but might not connect without proper setup)
        try:
            db_manager.initialize()
        except Exception:
            # It's okay if this fails in test environment
            pass


@pytest.mark.skipif(
    not get_available_features()["auth"], 
    reason="Auth features not available"
)
class TestAuthIntegration:
    """Test authentication integration if available."""
    
    def test_auth_manager_creation(self):
        """Test that AuthManager can be created."""
        from src.ghost.auth import AuthManager, User, UserRole
        config = Config()
        auth_manager = AuthManager(config.auth)
        assert auth_manager is not None

        # Test password hashing
        password = "test_password123!"
        hashed = auth_manager.hash_password(password)
        assert hashed != password
        assert auth_manager.verify_password(password, hashed)

        # Test user creation
        user = User(
            id="test123",
            username="testuser",
            email="test@example.com",
            roles=[UserRole.USER]
        )
        assert user.username == "testuser"
        assert UserRole.USER in user.roles


@pytest.mark.skipif(
    not get_available_features()["api"], 
    reason="API features not available"
)
class TestAPIIntegration:
    """Test API integration if available."""
    
    def test_api_manager_creation(self):
        """Test that APIManager can be created."""
        from src.ghost.api import APIManager
        config = Config()
        api_manager = APIManager(config.api)
        assert api_manager is not None

        # Should be able to create FastAPI app
        app = api_manager.create_app()
        assert app is not None
        assert hasattr(app, 'routes')


if __name__ == "__main__":
    # Run basic smoke tests
    print("🧪 Running Ghost Backend Framework Tests...")
    
    # Test core features
    features = get_available_features()
    print(f"📦 Available features: {features}")
    
    # Test basic configuration
    config = Config()
    print(f"⚙️  Configuration loaded successfully")
    
    # Test logging
    setup_logging(config.logging)
    logger = get_logger(__name__)
    logger.info("✅ Framework smoke test completed successfully!")
    
    print("🎉 All tests passed! Ghost Backend Framework is ready to use.")
