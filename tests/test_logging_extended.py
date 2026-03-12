"""Extended tests for src/ghost/logging.py — covers decorators and JSON sink."""

import json
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from src.ghost.logging import (
    LoggerMixin,
    LoggingManager,
    get_logger,
    log_async_function_call,
    log_function_call,
    setup_logging,
)


# ──────────────────────────────────────────────
# log_function_call decorator
# ──────────────────────────────────────────────

class TestLogFunctionCall:
    def test_decorator_success(self):
        @log_function_call
        def add(a, b):
            return a + b

        result = add(1, 2)
        assert result == 3

    def test_decorator_exception(self):
        @log_function_call
        def fail():
            raise ValueError("oops")

        with pytest.raises(ValueError, match="oops"):
            fail()


# ──────────────────────────────────────────────
# log_async_function_call decorator
# ──────────────────────────────────────────────

class TestLogAsyncFunctionCall:
    @pytest.mark.asyncio
    async def test_async_decorator_success(self):
        @log_async_function_call
        async def async_add(a, b):
            return a + b

        result = await async_add(3, 4)
        assert result == 7

    @pytest.mark.asyncio
    async def test_async_decorator_exception(self):
        @log_async_function_call
        async def async_fail():
            raise RuntimeError("async oops")

        with pytest.raises(RuntimeError, match="async oops"):
            await async_fail()


# ──────────────────────────────────────────────
# LoggingManager._json_sink
# ──────────────────────────────────────────────

class TestJsonSink:
    def test_json_sink_outputs_json(self):
        mgr = LoggingManager()
        from src.ghost.config import LoggingConfig
        config = LoggingConfig(level="DEBUG", json_output=True)

        captured = StringIO()
        with patch("sys.stderr", captured):
            mgr.setup(config)
            logger = mgr.get_logger("json-test")
            logger.info("test message")

        output = captured.getvalue()
        # Find a JSON line
        for line in output.strip().split("\n"):
            if line.strip():
                data = json.loads(line)
                assert "message" in data
                assert data["service"] == "ghost-backend"
                break


# ──────────────────────────────────────────────
# setup_logging module-level function
# ──────────────────────────────────────────────

class TestSetupLogging:
    def test_setup_logging_function(self):
        from src.ghost.config import LoggingConfig
        config = LoggingConfig(level="WARNING")
        setup_logging(config)
        # Should not raise
