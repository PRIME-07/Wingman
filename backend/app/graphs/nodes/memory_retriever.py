import time
from typing import Dict, Any
from backend.app.graphs.state import WingmanState
from backend.app.graphs.execution.helpers import emit_telemetry
from backend.app.telemetry.schemas import TelemetryEventType
from backend.app.tools.registry import tool_registry
from backend.app.tools.base.interface import ToolExecutionContext
from backend.app.core.logging import logger
from backend.app.core.utils import extract_text_content

async def memory_retriever_node(state: WingmanState) -> Dict[str, Any]:
    """
    Node responsible for pulling semantically relevant contextual 
    memories and vectors before reasoning decisions take place.
    """
    start_time = time.perf_counter()
    node_name = "memory_retriever"
    
    await emit_telemetry(
        state, 
        TelemetryEventType.NODE_STARTED, 
        node_name=node_name
    )
    
    # Extract last user input to query memory
    last_message = extract_text_content(state["messages"][-1].content) if state["messages"] else ""
    
    logger.info(f"[{node_name}] Skipping proactive memory retrieval per context policy.")
    retrieved_contexts = []

    duration_ms = (time.perf_counter() - start_time) * 1000
    
    await emit_telemetry(
        state,
        TelemetryEventType.NODE_COMPLETED,
        node_name=node_name,
        duration_ms=duration_ms
    )
    
    return {
        "retrieved_memories": retrieved_contexts,
        "active_node": node_name
    }
