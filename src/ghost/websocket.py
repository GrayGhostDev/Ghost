#!/usr/bin/env python3
"""
Ghost Backend Framework - WebSocket Support Module

Adds real-time communication capabilities to the backend.
"""

from typing import Dict, List, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import json
import asyncio
import uuid
from datetime import datetime

class WebSocketManager:
    """Manages WebSocket connections and real-time communications."""
    
    def __init__(self):
        # Store active connections by client ID
        self.active_connections: Dict[str, WebSocket] = {}
        # Store connections by frontend type
        self.frontend_connections: Dict[str, List[str]] = {}
        # Store channel subscriptions
        self.channel_subscriptions: Dict[str, List[str]] = {}
        
    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None, frontend_type: str = "unknown"):
        """Accept a WebSocket connection."""
        await websocket.accept()
        
        if not client_id:
            client_id = str(uuid.uuid4())
            
        self.active_connections[client_id] = websocket
        
        # Track by frontend type
        if frontend_type not in self.frontend_connections:
            self.frontend_connections[frontend_type] = []
        self.frontend_connections[frontend_type].append(client_id)
        
        print(f"🔌 WebSocket connected: {client_id} ({frontend_type})")
        
        # Send connection confirmation
        await self.send_personal_message(client_id, {
            "type": "connection",
            "message": "Connected successfully",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return client_id
    
    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            # Remove from frontend tracking
            for frontend_type, clients in self.frontend_connections.items():
                if client_id in clients:
                    clients.remove(client_id)
                    break
            
            # Remove from channel subscriptions
            for channel, subscribers in self.channel_subscriptions.items():
                if client_id in subscribers:
                    subscribers.remove(client_id)
            
            # Remove the connection
            del self.active_connections[client_id]
            print(f"❌ WebSocket disconnected: {client_id}")
    
    async def send_personal_message(self, client_id: str, message: Dict[str, Any]):
        """Send message to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            if websocket.application_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    print(f"Error sending to {client_id}: {e}")
                    self.disconnect(client_id)
    
    async def broadcast_to_frontend(self, frontend_type: str, message: Dict[str, Any]):
        """Send message to all connections of a specific frontend type."""
        if frontend_type in self.frontend_connections:
            clients = self.frontend_connections[frontend_type].copy()
            for client_id in clients:
                await self.send_personal_message(client_id, message)
    
    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Send message to all subscribers of a channel."""
        if channel in self.channel_subscriptions:
            subscribers = self.channel_subscriptions[channel].copy()
            for client_id in subscribers:
                await self.send_personal_message(client_id, message)
    
    async def subscribe_to_channel(self, client_id: str, channel: str):
        """Subscribe a client to a channel."""
        if channel not in self.channel_subscriptions:
            self.channel_subscriptions[channel] = []
        
        if client_id not in self.channel_subscriptions[channel]:
            self.channel_subscriptions[channel].append(client_id)
            
        await self.send_personal_message(client_id, {
            "type": "subscription",
            "message": f"Subscribed to channel: {channel}",
            "channel": channel
        })
    
    async def unsubscribe_from_channel(self, client_id: str, channel: str):
        """Unsubscribe a client from a channel."""
        if channel in self.channel_subscriptions:
            if client_id in self.channel_subscriptions[channel]:
                self.channel_subscriptions[channel].remove(client_id)
                
        await self.send_personal_message(client_id, {
            "type": "unsubscription", 
            "message": f"Unsubscribed from channel: {channel}",
            "channel": channel
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        return {
            "total_connections": len(self.active_connections),
            "frontend_connections": {
                frontend: len(clients) 
                for frontend, clients in self.frontend_connections.items()
            },
            "channel_subscriptions": {
                channel: len(subscribers)
                for channel, subscribers in self.channel_subscriptions.items()  
            }
        }


# Global WebSocket manager instance
ws_manager = WebSocketManager()


def add_websocket_routes(app: FastAPI):
    """Add WebSocket routes to the FastAPI app."""
    
    @app.websocket("/ws/{frontend_type}")
    async def websocket_endpoint(websocket: WebSocket, frontend_type: str):
        """Main WebSocket endpoint for frontend connections."""
        client_id = None
        try:
            client_id = await ws_manager.connect(websocket, frontend_type=frontend_type)
            
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    await handle_websocket_message(client_id, message)
                except json.JSONDecodeError:
                    await ws_manager.send_personal_message(client_id, {
                        "type": "error",
                        "message": "Invalid JSON format"
                    })
                    
        except WebSocketDisconnect:
            if client_id:
                ws_manager.disconnect(client_id)
    
    @app.get("/api/v1/websocket/stats")
    async def websocket_stats():
        """Get WebSocket connection statistics."""
        return ws_manager.get_stats()


async def handle_websocket_message(client_id: str, message: Dict[str, Any]):
    """Handle incoming WebSocket messages."""
    message_type = message.get("type")
    
    if message_type == "subscribe":
        channel = message.get("channel")
        if channel:
            await ws_manager.subscribe_to_channel(client_id, channel)
    
    elif message_type == "unsubscribe":
        channel = message.get("channel")
        if channel:
            await ws_manager.unsubscribe_from_channel(client_id, channel)
    
    elif message_type == "broadcast":
        # Broadcast to all clients of same frontend type
        frontend_type = message.get("frontend_type", "unknown")
        content = message.get("content", {})
        await ws_manager.broadcast_to_frontend(frontend_type, {
            "type": "broadcast",
            "from": client_id,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    elif message_type == "channel_message":
        # Send message to specific channel
        channel = message.get("channel")
        content = message.get("content", {})
        if channel:
            await ws_manager.broadcast_to_channel(channel, {
                "type": "channel_message",
                "channel": channel,
                "from": client_id,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    else:
        await ws_manager.send_personal_message(client_id, {
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        })


# Utility functions for sending notifications
async def send_frontend_notification(frontend_type: str, title: str, message: str, data: Optional[Dict] = None):
    """Send a notification to all clients of a frontend type."""
    await ws_manager.broadcast_to_frontend(frontend_type, {
        "type": "notification",
        "title": title,
        "message": message,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat()
    })


async def send_channel_update(channel: str, update_type: str, data: Dict[str, Any]):
    """Send an update to all subscribers of a channel."""
    await ws_manager.broadcast_to_channel(channel, {
        "type": "update",
        "update_type": update_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    })
