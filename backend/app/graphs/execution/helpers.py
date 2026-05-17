import time
from typing import Any, Dict, Optional
from datetime import datetime
from backend.app.telemetry.schemas import TelemetryEvent, TelemetryEventType
from backend.app.event_bus.bus import event_bus
from backend.app.graphs.state import WingmanState
from backend.app.core.logging import logger

async def emit_telemetry(
    state: WingmanState,
    event_type: TelemetryEventType,
    node_name: Optional[str] = None,
    tool_name: Optional[str] = None,
    payload: Dict[str, Any] = None,
    duration_ms: Optional[float] = None,
    emotion: Optional[str] = None,
    telemetry_label: Optional[str] = None
):
    """
    Constructs a standard telemetry event and publishes it to the internal
    asynchronous event bus for decoupled streaming and routing.
    """
    try:
        evt_payload = payload or {}
        if "priority_tier" not in evt_payload:
             evt_payload["priority_tier"] = state.get("priority_tier", "MEDIUM")
        
        if emotion:
            evt_payload["emotion"] = emotion
        if telemetry_label:
            evt_payload["telemetry_label"] = telemetry_label
        if "priority" not in evt_payload:
            evt_payload["priority"] = "ACTIVE" # Default priority for UX display
             
        event = TelemetryEvent(
            event_type=event_type,
            trace_id=state.get("trace_id", "unknown"),
            run_id=state.get("run_id", "unknown"),
            timestamp=datetime.utcnow(),
            node_name=node_name or state.get("active_node"),
            tool_name=tool_name,
            payload=evt_payload,
            duration_ms=duration_ms
        )
        
        # Publish to decoupled Event Bus with P6 Prioritization
        from backend.app.event_bus.bus import EventPriority
        
        priority = EventPriority.NORMAL
        if event_type in [TelemetryEventType.GRAPH_COMPLETED, TelemetryEventType.TOOL_FAILED]:
            priority = EventPriority.CRITICAL
        elif event_type in [TelemetryEventType.HITL_REQUESTED, TelemetryEventType.HITL_RESOLVED]:
            priority = EventPriority.HIGH
        elif event_type in [TelemetryEventType.TOKEN_STREAM]:
            priority = EventPriority.TRACE
            
        await event_bus.publish("telemetry", event, priority=priority)
        
    except Exception as e:
        logger.error(f"Failed publishing graph telemetry to bus: {e}")
