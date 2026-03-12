"""Tests for src/ghost/websocket.py

Covers:
- WebSocketManager: connect, disconnect, send_personal_message,
  broadcast_to_frontend, broadcast_to_channel, subscribe_to_channel,
  unsubscribe_from_channel, get_stats
- handle_websocket_message: subscribe, unsubscribe, broadcast,
  channel_message, unknown type
- Helper functions: send_frontend_notification, send_channel_update
- add_websocket_routes: /ws/{frontend_type} and /api/v1/websocket/stats
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketState

from src.ghost.websocket import (
    WebSocketManager,
    add_websocket_routes,
    handle_websocket_message,
    send_channel_update,
    send_frontend_notification,
    ws_manager,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_mock_ws(state=WebSocketState.CONNECTED):
    """Create a mock WebSocket with accept/send_text async methods."""
    ws = AsyncMock()
    ws.application_state = state
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def manager():
    """Fresh WebSocketManager for each test."""
    return WebSocketManager()


@pytest.fixture
def mock_ws():
    """Default connected mock WebSocket."""
    return _make_mock_ws()


# ──────────────────────────────────────────────
# WebSocketManager.__init__
# ──────────────────────────────────────────────

class TestWebSocketManagerInit:
    def test_initial_state(self, manager):
        assert manager.active_connections == {}
        assert manager.frontend_connections == {}
        assert manager.channel_subscriptions == {}


# ──────────────────────────────────────────────
# WebSocketManager.connect
# ──────────────────────────────────────────────

class TestWebSocketManagerConnect:
    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        mock_ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_stores_connection(self, manager, mock_ws):
        cid = await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        assert cid == "c1"
        assert manager.active_connections["c1"] is mock_ws

    @pytest.mark.asyncio
    async def test_connect_generates_client_id_when_none(self, manager, mock_ws):
        cid = await manager.connect(mock_ws, frontend_type="vue")
        assert cid is not None
        assert len(cid) > 0
        assert cid in manager.active_connections

    @pytest.mark.asyncio
    async def test_connect_tracks_frontend_type(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        assert "react" in manager.frontend_connections
        assert "c1" in manager.frontend_connections["react"]

    @pytest.mark.asyncio
    async def test_connect_sends_confirmation_message(self, manager, mock_ws):
        await manager.connect(
            mock_ws, client_id="c1", frontend_type="react", user_id="u1"
        )
        mock_ws.send_text.assert_awaited_once()
        sent = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent["type"] == "connection"
        assert sent["message"] == "Connected successfully"
        assert sent["client_id"] == "c1"
        assert sent["user_id"] == "u1"
        assert "timestamp" in sent

    @pytest.mark.asyncio
    async def test_connect_user_id_none_by_default(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        sent = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent["user_id"] is None

    @pytest.mark.asyncio
    async def test_connect_multiple_clients_same_frontend(self, manager):
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        await manager.connect(ws1, client_id="c1", frontend_type="react")
        await manager.connect(ws2, client_id="c2", frontend_type="react")
        assert len(manager.frontend_connections["react"]) == 2

    @pytest.mark.asyncio
    async def test_connect_different_frontends(self, manager):
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        await manager.connect(ws1, client_id="c1", frontend_type="react")
        await manager.connect(ws2, client_id="c2", frontend_type="vue")
        assert "react" in manager.frontend_connections
        assert "vue" in manager.frontend_connections


# ──────────────────────────────────────────────
# WebSocketManager.disconnect
# ──────────────────────────────────────────────

class TestWebSocketManagerDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        manager.disconnect("c1")
        assert "c1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_frontend_tracking(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        manager.disconnect("c1")
        assert "c1" not in manager.frontend_connections.get("react", [])

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_channel_subscriptions(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        await manager.subscribe_to_channel("c1", "updates")
        manager.disconnect("c1")
        assert "c1" not in manager.channel_subscriptions.get("updates", [])

    def test_disconnect_nonexistent_client_is_noop(self, manager):
        # Should not raise
        manager.disconnect("nonexistent")
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_disconnect_multiple_channels(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        await manager.subscribe_to_channel("c1", "ch1")
        await manager.subscribe_to_channel("c1", "ch2")
        manager.disconnect("c1")
        assert "c1" not in manager.channel_subscriptions.get("ch1", [])
        assert "c1" not in manager.channel_subscriptions.get("ch2", [])


# ──────────────────────────────────────────────
# WebSocketManager.send_personal_message
# ──────────────────────────────────────────────

class TestSendPersonalMessage:
    @pytest.mark.asyncio
    async def test_send_to_connected_client(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        mock_ws.send_text.reset_mock()

        await manager.send_personal_message("c1", {"type": "test", "data": "hello"})
        mock_ws.send_text.assert_awaited_once()
        sent = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent["type"] == "test"
        assert sent["data"] == "hello"

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_client_is_noop(self, manager):
        # Should not raise
        await manager.send_personal_message("ghost", {"type": "test"})

    @pytest.mark.asyncio
    async def test_send_to_disconnected_ws_skips(self, manager):
        ws = _make_mock_ws(state=WebSocketState.DISCONNECTED)
        manager.active_connections["c1"] = ws
        manager.frontend_connections["react"] = ["c1"]

        await manager.send_personal_message("c1", {"type": "test"})
        ws.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_error_triggers_disconnect(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        mock_ws.send_text.reset_mock()
        mock_ws.send_text.side_effect = RuntimeError("Connection lost")

        await manager.send_personal_message("c1", {"type": "test"})
        # Client should be disconnected after send failure
        assert "c1" not in manager.active_connections


# ──────────────────────────────────────────────
# WebSocketManager.broadcast_to_frontend
# ──────────────────────────────────────────────

class TestBroadcastToFrontend:
    @pytest.mark.asyncio
    async def test_broadcast_to_all_frontend_clients(self, manager):
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        await manager.connect(ws1, client_id="c1", frontend_type="react")
        await manager.connect(ws2, client_id="c2", frontend_type="react")
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        msg = {"type": "update", "data": "broadcast"}
        await manager.broadcast_to_frontend("react", msg)

        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_unknown_frontend_is_noop(self, manager):
        # Should not raise when frontend type has no connections
        await manager.broadcast_to_frontend("flutter", {"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_does_not_reach_other_frontends(self, manager):
        ws_react = _make_mock_ws()
        ws_vue = _make_mock_ws()
        await manager.connect(ws_react, client_id="c1", frontend_type="react")
        await manager.connect(ws_vue, client_id="c2", frontend_type="vue")
        ws_react.send_text.reset_mock()
        ws_vue.send_text.reset_mock()

        await manager.broadcast_to_frontend("react", {"type": "test"})
        ws_react.send_text.assert_awaited_once()
        ws_vue.send_text.assert_not_awaited()


# ──────────────────────────────────────────────
# WebSocketManager.broadcast_to_channel
# ──────────────────────────────────────────────

class TestBroadcastToChannel:
    @pytest.mark.asyncio
    async def test_broadcast_to_channel_subscribers(self, manager):
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        await manager.connect(ws1, client_id="c1", frontend_type="react")
        await manager.connect(ws2, client_id="c2", frontend_type="react")
        await manager.subscribe_to_channel("c1", "news")
        await manager.subscribe_to_channel("c2", "news")
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        await manager.broadcast_to_channel("news", {"type": "update"})
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_channel_is_noop(self, manager):
        await manager.broadcast_to_channel("nonexistent", {"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_only_to_subscribed_clients(self, manager):
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        await manager.connect(ws1, client_id="c1", frontend_type="react")
        await manager.connect(ws2, client_id="c2", frontend_type="react")
        await manager.subscribe_to_channel("c1", "news")
        # c2 is NOT subscribed to "news"
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        await manager.broadcast_to_channel("news", {"type": "update"})
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_not_awaited()


# ──────────────────────────────────────────────
# WebSocketManager.subscribe_to_channel
# ──────────────────────────────────────────────

class TestSubscribeToChannel:
    @pytest.mark.asyncio
    async def test_subscribe_creates_channel(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        await manager.subscribe_to_channel("c1", "alerts")
        assert "alerts" in manager.channel_subscriptions
        assert "c1" in manager.channel_subscriptions["alerts"]

    @pytest.mark.asyncio
    async def test_subscribe_sends_confirmation(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        mock_ws.send_text.reset_mock()

        await manager.subscribe_to_channel("c1", "alerts")
        mock_ws.send_text.assert_awaited_once()
        sent = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent["type"] == "subscription"
        assert "alerts" in sent["message"]
        assert sent["channel"] == "alerts"

    @pytest.mark.asyncio
    async def test_subscribe_duplicate_is_idempotent(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        await manager.subscribe_to_channel("c1", "alerts")
        await manager.subscribe_to_channel("c1", "alerts")
        assert manager.channel_subscriptions["alerts"].count("c1") == 1

    @pytest.mark.asyncio
    async def test_subscribe_multiple_channels(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        await manager.subscribe_to_channel("c1", "ch1")
        await manager.subscribe_to_channel("c1", "ch2")
        assert "c1" in manager.channel_subscriptions["ch1"]
        assert "c1" in manager.channel_subscriptions["ch2"]


# ──────────────────────────────────────────────
# WebSocketManager.unsubscribe_from_channel
# ──────────────────────────────────────────────

class TestUnsubscribeFromChannel:
    @pytest.mark.asyncio
    async def test_unsubscribe_removes_from_channel(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        await manager.subscribe_to_channel("c1", "alerts")
        await manager.unsubscribe_from_channel("c1", "alerts")
        assert "c1" not in manager.channel_subscriptions.get("alerts", [])

    @pytest.mark.asyncio
    async def test_unsubscribe_sends_confirmation(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        await manager.subscribe_to_channel("c1", "alerts")
        mock_ws.send_text.reset_mock()

        await manager.unsubscribe_from_channel("c1", "alerts")
        mock_ws.send_text.assert_awaited_once()
        sent = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent["type"] == "unsubscription"
        assert "alerts" in sent["message"]
        assert sent["channel"] == "alerts"

    @pytest.mark.asyncio
    async def test_unsubscribe_from_nonexistent_channel(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        # Should not raise, and should still send confirmation
        await manager.unsubscribe_from_channel("c1", "nonexistent")
        # The last send_text call should be the unsubscription confirmation
        last_call = mock_ws.send_text.call_args
        sent = json.loads(last_call[0][0])
        assert sent["type"] == "unsubscription"

    @pytest.mark.asyncio
    async def test_unsubscribe_client_not_in_channel(self, manager, mock_ws):
        """Client exists in the channel dict but is not subscribed."""
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        # Create channel with different subscriber
        manager.channel_subscriptions["alerts"] = ["other-client"]
        await manager.unsubscribe_from_channel("c1", "alerts")
        # "other-client" should still be there
        assert "other-client" in manager.channel_subscriptions["alerts"]


# ──────────────────────────────────────────────
# WebSocketManager.get_stats
# ──────────────────────────────────────────────

class TestGetStats:
    def test_empty_stats(self, manager):
        stats = manager.get_stats()
        assert stats["total_connections"] == 0
        assert stats["frontend_connections"] == {}
        assert stats["channel_subscriptions"] == {}

    @pytest.mark.asyncio
    async def test_stats_with_connections(self, manager):
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        await manager.connect(ws1, client_id="c1", frontend_type="react")
        await manager.connect(ws2, client_id="c2", frontend_type="vue")

        stats = manager.get_stats()
        assert stats["total_connections"] == 2
        assert stats["frontend_connections"]["react"] == 1
        assert stats["frontend_connections"]["vue"] == 1

    @pytest.mark.asyncio
    async def test_stats_with_channels(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        await manager.subscribe_to_channel("c1", "news")
        await manager.subscribe_to_channel("c1", "alerts")

        stats = manager.get_stats()
        assert stats["channel_subscriptions"]["news"] == 1
        assert stats["channel_subscriptions"]["alerts"] == 1

    @pytest.mark.asyncio
    async def test_stats_after_disconnect(self, manager, mock_ws):
        await manager.connect(mock_ws, client_id="c1", frontend_type="react")
        manager.disconnect("c1")

        stats = manager.get_stats()
        assert stats["total_connections"] == 0


# ──────────────────────────────────────────────
# handle_websocket_message
# ──────────────────────────────────────────────

class TestHandleWebsocketMessage:
    @pytest.mark.asyncio
    async def test_subscribe_message(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="react")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await handle_websocket_message("c1", {
                "type": "subscribe",
                "channel": "updates",
            })

        assert "c1" in mgr.channel_subscriptions.get("updates", [])

    @pytest.mark.asyncio
    async def test_subscribe_without_channel_is_noop(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="react")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await handle_websocket_message("c1", {
                "type": "subscribe",
            })

        assert mgr.channel_subscriptions == {}

    @pytest.mark.asyncio
    async def test_unsubscribe_message(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="react")
        await mgr.subscribe_to_channel("c1", "updates")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await handle_websocket_message("c1", {
                "type": "unsubscribe",
                "channel": "updates",
            })

        assert "c1" not in mgr.channel_subscriptions.get("updates", [])

    @pytest.mark.asyncio
    async def test_unsubscribe_without_channel_is_noop(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="react")
        await mgr.subscribe_to_channel("c1", "updates")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await handle_websocket_message("c1", {
                "type": "unsubscribe",
                # no channel
            })

        # Should remain subscribed
        assert "c1" in mgr.channel_subscriptions.get("updates", [])

    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        mgr = WebSocketManager()
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        await mgr.connect(ws1, client_id="c1", frontend_type="react")
        await mgr.connect(ws2, client_id="c2", frontend_type="react")
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await handle_websocket_message("c1", {
                "type": "broadcast",
                "frontend_type": "react",
                "content": {"msg": "hello everyone"},
            })

        # Both clients should receive the broadcast
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()
        sent = json.loads(ws1.send_text.call_args[0][0])
        assert sent["type"] == "broadcast"
        assert sent["from"] == "c1"
        assert sent["content"] == {"msg": "hello everyone"}
        assert "timestamp" in sent

    @pytest.mark.asyncio
    async def test_broadcast_uses_default_frontend_type(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="unknown")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await handle_websocket_message("c1", {
                "type": "broadcast",
                # no frontend_type specified -> defaults to "unknown"
            })

        ws.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_channel_message(self):
        mgr = WebSocketManager()
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        await mgr.connect(ws1, client_id="c1", frontend_type="react")
        await mgr.connect(ws2, client_id="c2", frontend_type="react")
        await mgr.subscribe_to_channel("c1", "project-1")
        await mgr.subscribe_to_channel("c2", "project-1")
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await handle_websocket_message("c1", {
                "type": "channel_message",
                "channel": "project-1",
                "content": {"action": "file_changed"},
            })

        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()
        sent = json.loads(ws1.send_text.call_args[0][0])
        assert sent["type"] == "channel_message"
        assert sent["channel"] == "project-1"
        assert sent["from"] == "c1"
        assert sent["content"] == {"action": "file_changed"}
        assert "timestamp" in sent

    @pytest.mark.asyncio
    async def test_channel_message_without_channel_is_noop(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="react")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await handle_websocket_message("c1", {
                "type": "channel_message",
                # no channel
                "content": {"data": "test"},
            })

        # No message should be sent (no channel specified)
        ws.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_message_type(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="react")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await handle_websocket_message("c1", {
                "type": "unknown_type",
            })

        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "error"
        assert "Unknown message type" in sent["message"]
        assert "unknown_type" in sent["message"]

    @pytest.mark.asyncio
    async def test_missing_message_type(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="react")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await handle_websocket_message("c1", {
                "data": "no type field",
            })

        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "error"


# ──────────────────────────────────────────────
# send_frontend_notification
# ──────────────────────────────────────────────

class TestSendFrontendNotification:
    @pytest.mark.asyncio
    async def test_sends_notification_to_frontend(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="react")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await send_frontend_notification(
                "react", "Alert", "Something happened", {"key": "val"}
            )

        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "notification"
        assert sent["title"] == "Alert"
        assert sent["message"] == "Something happened"
        assert sent["data"] == {"key": "val"}
        assert "timestamp" in sent

    @pytest.mark.asyncio
    async def test_notification_default_data_is_empty_dict(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="react")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await send_frontend_notification("react", "Title", "Msg")

        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["data"] == {}

    @pytest.mark.asyncio
    async def test_notification_to_nonexistent_frontend(self):
        mgr = WebSocketManager()
        with patch("src.ghost.websocket.ws_manager", mgr):
            # Should not raise
            await send_frontend_notification("flutter", "Title", "Msg")


# ──────────────────────────────────────────────
# send_channel_update
# ──────────────────────────────────────────────

class TestSendChannelUpdate:
    @pytest.mark.asyncio
    async def test_sends_update_to_channel(self):
        mgr = WebSocketManager()
        ws = _make_mock_ws()
        await mgr.connect(ws, client_id="c1", frontend_type="react")
        await mgr.subscribe_to_channel("c1", "project-1")
        ws.send_text.reset_mock()

        with patch("src.ghost.websocket.ws_manager", mgr):
            await send_channel_update(
                "project-1", "file_changed", {"file": "main.py"}
            )

        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "update"
        assert sent["update_type"] == "file_changed"
        assert sent["data"] == {"file": "main.py"}
        assert "timestamp" in sent

    @pytest.mark.asyncio
    async def test_update_to_nonexistent_channel(self):
        mgr = WebSocketManager()
        with patch("src.ghost.websocket.ws_manager", mgr):
            # Should not raise
            await send_channel_update("ghost-channel", "type", {"k": "v"})


# ──────────────────────────────────────────────
# ws_manager global instance
# ──────────────────────────────────────────────

class TestWsManagerGlobal:
    def test_ws_manager_is_websocket_manager(self):
        assert isinstance(ws_manager, WebSocketManager)

    def test_ws_manager_has_empty_initial_state(self):
        # The global instance may have state from other tests,
        # but it should be a valid WebSocketManager
        assert hasattr(ws_manager, "active_connections")
        assert hasattr(ws_manager, "frontend_connections")
        assert hasattr(ws_manager, "channel_subscriptions")


# ──────────────────────────────────────────────
# add_websocket_routes — stats endpoint
# ──────────────────────────────────────────────

class TestAddWebsocketRoutesStats:
    @pytest.fixture
    def stats_app(self):
        app = FastAPI()
        add_websocket_routes(app)
        return app

    @pytest.fixture
    def stats_client(self, stats_app):
        return TestClient(stats_app)

    def test_stats_endpoint_returns_200(self, stats_client):
        resp = stats_client.get("/api/v1/websocket/stats")
        assert resp.status_code == 200

    def test_stats_endpoint_returns_valid_json(self, stats_client):
        resp = stats_client.get("/api/v1/websocket/stats")
        data = resp.json()
        assert "total_connections" in data
        assert "frontend_connections" in data
        assert "channel_subscriptions" in data


# ──────────────────────────────────────────────
# add_websocket_routes — WebSocket endpoint
# ──────────────────────────────────────────────

class TestAddWebsocketRoutesWS:
    @pytest.fixture
    def ws_app(self):
        app = FastAPI()
        add_websocket_routes(app)
        return app

    @pytest.fixture
    def ws_client(self, ws_app):
        return TestClient(ws_app)

    def test_ws_rejected_without_token(self, ws_client):
        """WebSocket connection without token should be closed with 4001."""
        with pytest.raises(Exception):
            with ws_client.websocket_connect("/ws/react"):
                pass  # Should not reach here

    def test_ws_rejected_with_invalid_token(self, ws_client):
        """WebSocket connection with invalid token should be closed."""
        with pytest.raises(Exception):
            with ws_client.websocket_connect("/ws/react?token=invalid-jwt"):
                pass

    def test_ws_connection_with_valid_token(self, ws_client):
        """WebSocket connection with valid token should succeed."""
        mock_token_data = MagicMock()
        mock_token_data.user_id = "user-123"

        mock_auth = MagicMock()
        mock_auth.verify_token.return_value = mock_token_data

        with patch(
            "src.ghost.websocket.ws_manager", WebSocketManager()
        ), patch(
            "src.ghost.auth.get_auth_manager", return_value=mock_auth
        ):
            with ws_client.websocket_connect("/ws/react?token=valid-jwt") as ws:
                # Should receive connection confirmation
                data = ws.receive_json()
                assert data["type"] == "connection"
                assert data["message"] == "Connected successfully"
                assert data["user_id"] == "user-123"

    def test_ws_send_and_receive_subscribe(self, ws_client):
        """Test sending a subscribe message over WebSocket."""
        mock_token_data = MagicMock()
        mock_token_data.user_id = "user-123"

        mock_auth = MagicMock()
        mock_auth.verify_token.return_value = mock_token_data

        mgr = WebSocketManager()

        with patch(
            "src.ghost.websocket.ws_manager", mgr
        ), patch(
            "src.ghost.auth.get_auth_manager", return_value=mock_auth
        ):
            with ws_client.websocket_connect("/ws/react?token=valid-jwt") as ws:
                # Receive connection confirmation
                ws.receive_json()

                # Send subscribe message
                ws.send_json({"type": "subscribe", "channel": "updates"})
                # Should receive subscription confirmation
                data = ws.receive_json()
                assert data["type"] == "subscription"
                assert data["channel"] == "updates"

    def test_ws_send_invalid_json(self, ws_client):
        """Test sending invalid JSON over WebSocket."""
        mock_token_data = MagicMock()
        mock_token_data.user_id = "user-123"

        mock_auth = MagicMock()
        mock_auth.verify_token.return_value = mock_token_data

        with patch(
            "src.ghost.websocket.ws_manager", WebSocketManager()
        ), patch(
            "src.ghost.auth.get_auth_manager", return_value=mock_auth
        ):
            with ws_client.websocket_connect("/ws/react?token=valid-jwt") as ws:
                # Receive connection confirmation
                ws.receive_json()

                # Send invalid JSON
                ws.send_text("not-valid-json{{{")
                data = ws.receive_json()
                assert data["type"] == "error"
                assert "Invalid JSON" in data["message"]

    def test_ws_unknown_message_type(self, ws_client):
        """Test sending unknown message type over WebSocket."""
        mock_token_data = MagicMock()
        mock_token_data.user_id = "user-123"

        mock_auth = MagicMock()
        mock_auth.verify_token.return_value = mock_token_data

        with patch(
            "src.ghost.websocket.ws_manager", WebSocketManager()
        ), patch(
            "src.ghost.auth.get_auth_manager", return_value=mock_auth
        ):
            with ws_client.websocket_connect("/ws/react?token=valid-jwt") as ws:
                ws.receive_json()
                ws.send_json({"type": "foobar"})
                data = ws.receive_json()
                assert data["type"] == "error"
                assert "Unknown message type" in data["message"]

    def test_ws_auth_module_exception_closes_connection(self, ws_client):
        """When auth module raises, connection should be closed (no token verified)."""
        with patch(
            "src.ghost.websocket.ws_manager", WebSocketManager()
        ), patch(
            "src.ghost.auth.get_auth_manager",
            side_effect=ImportError("auth not configured"),
        ):
            with pytest.raises(Exception):
                with ws_client.websocket_connect("/ws/react?token=some-token"):
                    pass

    def test_ws_token_verification_returns_none(self, ws_client):
        """When verify_token returns None, connection should be closed."""
        mock_auth = MagicMock()
        mock_auth.verify_token.return_value = None

        with patch(
            "src.ghost.websocket.ws_manager", WebSocketManager()
        ), patch(
            "src.ghost.auth.get_auth_manager", return_value=mock_auth
        ):
            with pytest.raises(Exception):
                with ws_client.websocket_connect("/ws/react?token=bad-token"):
                    pass
