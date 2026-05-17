from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.app.telemetry.manager import telemetry_manager
from backend.app.core.logging import logger

router = APIRouter()

@router.websocket("/ws")
async def telemetry_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for broadcasting live agent reasoning, 
    node transitions, tool usage, and system traces to client dashboards.
    """
    await telemetry_manager.connect(websocket)
    try:
        # Keep context active, listen for client heartbeats/responses if needed
        while True:
            # Discard/log incoming client messages - telemetry is primarily push-based
            data = await websocket.receive_text()
            logger.debug(f"Telemetry heartbeat received from client: {data}")
    except WebSocketDisconnect:
        telemetry_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Telemetry WebSocket error: {e}")
        telemetry_manager.disconnect(websocket)
