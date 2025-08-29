"""
Logging Module

Centralized logging setup using loguru for enhanced logging capabilities.
Supports file rotation, structured logging, and multiple output formats.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
from .config import get_config


class LoggingManager:
    """Manages logging configuration and setup."""
    
    def __init__(self):
        self._configured = False
        self._loggers: Dict[str, Any] = {}
    
    def setup(self, config: Optional[Any] = None) -> None:
        """Set up logging configuration."""
        if self._configured:
            return
        
        if config is None:
            config = get_config().logging
        
        # Remove default logger
        logger.remove()
        
        # Add console handler with colors
        logger.add(
            sys.stderr,
            level=config.level,
            format=config.format,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
        
        # Add file handler if specified
        if config.file_path:
            log_path = Path(config.file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                log_path,
                level=config.level,
                format=config.format,
                rotation=config.max_size,
                retention=config.retention,
                compression=config.compression,
                backtrace=True,
                diagnose=True,
            )
        
        self._configured = True
    
    def get_logger(self, name: str) -> Any:
        """Get a named logger instance."""
        if not self._configured:
            self.setup()
        
        if name not in self._loggers:
            self._loggers[name] = logger.bind(name=name)
        
        return self._loggers[name]


# Global logging manager
_logging_manager = LoggingManager()


def setup_logging(config: Optional[Any] = None) -> None:
    """Set up global logging configuration."""
    _logging_manager.setup(config)


def get_logger(name: str = "ghost") -> Any:
    """Get a logger instance."""
    return _logging_manager.get_logger(name)


# Create some commonly used loggers
app_logger = get_logger("app")
api_logger = get_logger("api")
db_logger = get_logger("database")
auth_logger = get_logger("auth")
task_logger = get_logger("tasks")


class LoggerMixin:
    """Mixin to add logging capabilities to any class."""
    
    @property
    def logger(self):
        """Get logger for this class."""
        class_name = self.__class__.__name__.lower()
        return get_logger(class_name)


def log_function_call(func):
    """Decorator to log function calls."""
    def wrapper(*args, **kwargs):
        logger = get_logger("functions")
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed with error: {e}")
            raise
    return wrapper


def log_async_function_call(func):
    """Decorator to log async function calls."""
    async def wrapper(*args, **kwargs):
        logger = get_logger("async_functions")
        logger.debug(f"Calling async {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"Async {func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Async {func.__name__} failed with error: {e}")
            raise
    return wrapper
