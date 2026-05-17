from typing import Literal
from backend.app.graphs.state import WingmanState
from backend.app.core.logging import logger

def routing_decision(state: WingmanState) -> str:
    """
    Decides execution direction based on message output states.
    Routes tool execution tracks to specialized sub-agents, or transitions to Reflection.
    """
    messages = state.get("messages", [])
    if not messages:
        return "reflection"
        
    last_message = messages[-1]
    
    # Check if the LLM requests additional tooling logic
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_call = last_message.tool_calls[0]
        tool_name = tool_call.get("name", "")
        
        if tool_name == "delegate_to_web_agent":
            logger.info(f"[Router] Tool invocation directives active. Routing to: web_agent.")
            return "web_agent"
        elif tool_name == "delegate_to_comm_agent":
            logger.info(f"[Router] Tool invocation directives active. Routing to: comm_agent.")
            return "comm_agent"
        elif tool_name == "delegate_to_work_agent":
            logger.info(f"[Router] Tool invocation directives active. Routing to: work_agent.")
            return "work_agent"
        elif tool_name == "delegate_to_rag_agent":
            logger.info(f"[Router] Tool invocation directives active. Routing to: rag_agent.")
            return "rag_agent"
        else:
            # Fallback legacy executor just in case
            logger.info(f"[Router] Fallback route to: tool_executor.")
            return "tool_executor"
            
            
    # Complete orchestrator logic, pass control to cognitive reflection layer
    logger.info("[Router] Tool directives satisfied. Transferring control to: reflection node.")
    return "reflection"
