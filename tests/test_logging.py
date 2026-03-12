"""Tests for src/ghost/logging.py"""

import json
import pytest
from io import StringIO
from unittest.mock import patch

from src.ghost.config import LoggingConfig
from src.ghost.logging import LoggerMixin, LoggingManager, get_logger


class TestLoggingManager:
    def test_setup_default(self):
        mgr = LoggingManager()
        config = LoggingConfig(level="DEBUG")
        mgr.setup(config)
        assert mgr._configured is True

    def test_setup_idempotent(self):
        mgr = LoggingManager()
        config = LoggingConfig(level="INFO")
        mgr.setup(config)
        mgr.setup(config)  # should not raise

    def test_setup_json_mode(self):
        mgr = LoggingManager()
        config = LoggingConfig(level="INFO", json_output=True)
        mgr.setup(config)
        assert mgr._configured is True

    def test_setup_file_mode(self, tmp_path):
        mgr = LoggingManager()
        log_file = tmp_path / "test.log"
        config = LoggingConfig(level="DEBUG", file_path=str(log_file))
        mgr.setup(config)
        assert mgr._configured is True

    def test_get_logger(self):
        mgr = LoggingManager()
        config = LoggingConfig(level="DEBUG")
        mgr.setup(config)
        logger = mgr.get_logger("test-logger")
        assert logger is not None

    def test_get_logger_cached(self):
        mgr = LoggingManager()
        config = LoggingConfig(level="DEBUG")
        mgr.setup(config)
        l1 = mgr.get_logger("same")
        l2 = mgr.get_logger("same")
        assert l1 is l2

    def test_get_logger_auto_setup(self):
        mgr = LoggingManager()
        logger = mgr.get_logger("auto")
        assert logger is not None
        assert mgr._configured is True


class TestGetLogger:
    def test_module_level_get_logger(self):
        logger = get_logger("mymodule")
        assert logger is not None


class TestLoggerMixin:
    def test_mixin_property(self):
        class MyClass(LoggerMixin):
            pass

        obj = MyClass()
        logger = obj.logger
        assert logger is not None
