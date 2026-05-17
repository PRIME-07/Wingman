import json
from typing import List, Any
from fastapi import WebSocket
from backend.app.core.logging import logger
from backend.app.telemetry.schemas import TelemetryEvent

class TelemetryManager:
    """
    Coordinates real-time telemetry websocket connections, 
    enforcing serialization of structured TelemetryEvent models.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.debug(f"[Telemetry] WebSocket added. Sessions={len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.debug(f"[Telemetry] WebSocket removed. Sessions={len(self.active_connections)}")

    async def broadcast(self, event: Any):
        """
        Validates and broadcasts standard telemetry events to all clients.
        Handles both Pydantic models and raw dictionaries.
        """
        if not self.active_connections:
            return
            
        try:
            if hasattr(event, "model_dump_json"):
                event_data = event.model_dump_json()
            else:
                event_data = json.dumps(event)
        except Exception as e:
            logger.error(f"Telemetry serialization failed: {e}")
            return

        dead_sockets = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(event_data)
            except Exception as e:
                logger.error(f"Telemetry broadcast failed for socket: {e}")
                dead_sockets.append(connection)
                
        for dead in dead_sockets:
            self.disconnect(dead)

# Singleton access instance
telemetry_manager = TelemetryManager()

