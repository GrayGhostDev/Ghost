"""Tests for src/ghost/api.py"""

import time
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.ghost.api import APIManager, APIResponse, RequestTracker
from src.ghost.config import Config, set_config


@pytest.fixture
def test_app(test_config):
    """Create a test FastAPI app (named test_app to avoid pytest-flask 'app' conflict)."""
    mgr = APIManager(test_config.api)
    return mgr.create_app(title="Test App", version="0.1.0")


@pytest.fixture
def client(test_app):
    """TestClient for the test app."""
    return TestClient(test_app)


# ──────────────────────────────────────────────
# APIResponse
# ──────────────────────────────────────────────

class TestAPIResponse:
    def test_success_default(self):
        r = APIResponse.success()
        assert r["success"] is True
        assert r["message"] == "Success"
        assert r["data"] is None
        assert "timestamp" in r

    def test_success_with_data(self):
        r = APIResponse.success(data={"k": "v"}, message="OK")
        assert r["data"] == {"k": "v"}
        assert r["message"] == "OK"

    def test_success_with_meta(self):
        r = APIResponse.success(meta={"extra": 1})
        assert r["meta"]["extra"] == 1

    def test_error_default(self):
        r = APIResponse.error()
        assert r["success"] is False
        assert r["error"]["code"] == 400

    def test_error_custom(self):
        r = APIResponse.error(message="Not found", code=404, details={"id": "x"})
        assert r["message"] == "Not found"
        assert r["error"]["code"] == 404
        assert r["error"]["details"]["id"] == "x"

    def test_paginated(self):
        r = APIResponse.paginated(data=[1, 2, 3], page=1, per_page=10, total=25)
        assert r["success"] is True
        meta = r["meta"]["pagination"]
        assert meta["page"] == 1
        assert meta["per_page"] == 10
        assert meta["total"] == 25
        assert meta["pages"] == 3

    def test_paginated_exact_pages(self):
        r = APIResponse.paginated(data=[], page=1, per_page=5, total=10)
        assert r["meta"]["pagination"]["pages"] == 2


# ──────────────────────────────────────────────
# RequestTracker
# ──────────────────────────────────────────────

class TestRequestTracker:
    def test_start_and_end_request(self):
        tracker = RequestTracker()
        tracker.start_request("r1", "/api", "GET", "127.0.0.1")
        assert "r1" in tracker.requests
        assert tracker.requests["r1"]["status"] == "in_progress"

        tracker.end_request("r1", 200)
        assert tracker.requests["r1"]["status"] == "completed"
        assert tracker.requests["r1"]["status_code"] == 200
        assert "duration" in tracker.requests["r1"]

    def test_end_nonexistent_request(self):
        tracker = RequestTracker()
        tracker.end_request("missing", 200)  # no error


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

class TestRootEndpoint:
    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "Ghost" in body["data"]["name"]


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """Health endpoint works when DB and Redis mocks are healthy."""
        # The health endpoint imports get_db_manager/get_redis_manager locally,
        # and database.py may not import cleanly (pymongo missing). Create a
        # fake database module in sys.modules so the local import succeeds.
        import sys
        import types

        fake_db_mod = types.ModuleType("src.ghost.database")
        mock_db_mgr = MagicMock()
        mock_db_mgr.health_check.return_value = True
        mock_redis_mgr = MagicMock()
        mock_redis_mgr.health_check.return_value = True
        fake_db_mod.get_db_manager = MagicMock(return_value=mock_db_mgr)
        fake_db_mod.get_redis_manager = MagicMock(return_value=mock_redis_mgr)

        with patch.dict(sys.modules, {"src.ghost.database": fake_db_mod}):
            r = client.get("/health")
            assert r.status_code == 200
            body = r.json()
            assert body["data"]["api"] == "healthy"

    def test_health_db_error(self, client):
        """Health endpoint reports errors when DB/Redis unavailable."""
        import sys
        import types

        fake_db_mod = types.ModuleType("src.ghost.database")
        fake_db_mod.get_db_manager = MagicMock(side_effect=Exception("no db"))
        fake_db_mod.get_redis_manager = MagicMock(side_effect=Exception("no redis"))

        with patch.dict(sys.modules, {"src.ghost.database": fake_db_mod}):
            r = client.get("/health")
            assert r.status_code == 200
            body = r.json()
            assert "error" in body["data"]["database"]


class TestMetricsEndpoint:
    def test_metrics_fallback(self, client):
        """Without prometheus_client, returns JSON metrics."""
        with patch("src.ghost.api.PROMETHEUS_AVAILABLE", False):
            r = client.get("/metrics")
            assert r.status_code == 200


class TestTokenEndpoint:
    def test_token_stub(self, client):
        r = client.post("/token")
        assert r.status_code == 501


class TestLoginEndpoint:
    def test_login_stub(self, client):
        r = client.post("/login")
        assert r.status_code == 501


class TestForgotPasswordEndpoint:
    def test_forgot_password_success(self, client):
        r = client.post("/forgot-password", json={"email": "test@example.com"})
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert "reset link" in r.json()["message"]

    def test_forgot_password_no_body(self, client):
        r = client.post("/forgot-password", content=b"not json",
                        headers={"content-type": "application/json"})
        assert r.status_code == 200  # always 200 to prevent enumeration


class TestResetPasswordEndpoint:
    def test_reset_password_missing_fields(self, client):
        r = client.post("/reset-password", json={"token": "x"})
        assert r.status_code == 400

    def test_reset_password_invalid_token(self, client):
        r = client.post("/reset-password", json={
            "token": "invalid.token.here",
            "new_password": "newpass123!",
        })
        assert r.status_code == 400
        body = r.json()
        msg = body.get("detail", body.get("message", "")).lower()
        assert "expired" in msg or "invalid" in msg

    def test_reset_password_valid_token(self, client, test_config):
        from src.ghost.auth import AuthManager

        mgr = AuthManager(test_config.auth)
        token = mgr.create_reset_token("user@test.com", "user-99")

        r = client.post("/reset-password", json={
            "token": token,
            "new_password": "newsecret123!",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["user_id"] == "user-99"

    def test_reset_password_bad_json(self, client):
        r = client.post("/reset-password", content=b"not json",
                        headers={"content-type": "application/json"})
        assert r.status_code == 400


# ──────────────────────────────────────────────
# Request headers
# ──────────────────────────────────────────────

class TestRequestHeaders:
    def test_request_id_header(self, client):
        r = client.get("/")
        assert "x-request-id" in r.headers

    def test_process_time_header(self, client):
        r = client.get("/")
        assert "x-process-time" in r.headers


# ──────────────────────────────────────────────
# Exception handlers
# ──────────────────────────────────────────────

class TestExceptionHandlers:
    def test_http_exception_format(self, client):
        r = client.post("/token")  # returns 501
        body = r.json()
        assert body["success"] is False
        assert body["error"]["code"] == 501

    def test_general_exception_handler(self, test_config):
        """Test that unhandled exceptions return 500 JSON response."""
        mgr = APIManager(test_config.api)
        fresh_app = mgr.create_app(title="Boom Test")

        @fresh_app.get("/boom")
        async def boom():
            raise RuntimeError("kaboom")

        c = TestClient(fresh_app, raise_server_exceptions=False)
        r = c.get("/boom")
        assert r.status_code == 500
        body = r.json()
        assert body["success"] is False
        assert body["error"]["code"] == 500
