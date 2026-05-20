import time
import json
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from backend.app.graphs.state import WingmanState
from backend.app.graphs.execution.helpers import emit_telemetry
from backend.app.telemetry.schemas import TelemetryEventType
from backend.app.services.llm.client import get_llm
from backend.app.prompts.registry import prompt_registry
from backend.app.tools.delegation_tools import get_delegation_tools
from backend.app.core.logging import logger

async def orchestrator_node(state: WingmanState) -> Dict[str, Any]:
    """
    Main decision node. Injects base prompt context, executes LLM 
    reasoning cycle, streams intermediate token outputs, and returns 
    messages/tool invocations.
    """
    start_time = time.perf_counter()
    node_name = "orchestrator"
    
    await emit_telemetry(
        state, 
        TelemetryEventType.NODE_STARTED, 
        node_name=node_name
    )
    
    # 0. Detect and handle successful communication HITL events (Gmail/Slack send success)
    if state.get("messages"):
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "type") and last_msg.type == "tool":
            # Search backwards for the tool name corresponding to the ToolMessage's tool_call_id
            tool_name = None
            for msg in reversed(state["messages"][:-1]):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc.get("id") == last_msg.tool_call_id:
                            tool_name = tc.get("name")
                            break
                if tool_name:
                    break
            
            if tool_name == "delegate_to_comm_agent":
                content_lower = str(last_msg.content).lower()
                # Check for failure/rejection/cancellation or refinement signals
                is_rejection_failure_or_refine = any(
                    word in content_lower 
                    for word in ["reject", "cancel", "deny", "fail", "error", "refine"]
                )
                
                # If there is no rejection, failure, or refinement request, it was a successful send/post!
                if not is_rejection_failure_or_refine:
                    from backend.app.core.utils import extract_text_content
                    confirm_text = extract_text_content(last_msg.content)
                    logger.info(f"[Orchestrator] Direct communication success detected for tool '{tool_name}'. Short-circuiting LLM with: '{confirm_text}'")
                    
                    # Emit token stream for the response so it is visible in real-time
                    await emit_telemetry(
                        state, 
                        TelemetryEventType.TOKEN_STREAM, 
                        node_name=node_name,
                        payload={"token": confirm_text}
                    )
                    
                    updates = {
                        "messages": [AIMessage(content=confirm_text)],
                        "active_node": node_name,
                        "active_tool_calls": []
                    }
                    
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    await emit_telemetry(
                        state,
                        TelemetryEventType.NODE_COMPLETED,
                        node_name=node_name,
                        duration_ms=duration_ms
                    )
                    return updates

    
    # 1. Compile and Compress Working Memory (Token Budgeting)
    from backend.app.cognition.working_memory import working_memory_compiler
    
    current_summary = state.get("working_memory_summary", "")
    recent_messages, updated_summary, summary_was_updated = await working_memory_compiler.compile_and_budget(
        messages=state["messages"],
        current_summary=current_summary
    )
    
    # 2. Build Dynamic Prompt
    system_instructions = prompt_registry.get_prompt("orchestrator_system")
    
    # Inject distilled working memory summary if it exists
    active_summary = updated_summary or current_summary
    if active_summary:
        system_instructions += f"\n\n[WORKING CONTEXT SUMMARY]\nRecent chronological summary:\n{active_summary}"
    
    # Incorporate task execution plan if present
    active_plan = state.get("execution_plan")
    if active_plan:
        plan_block = json.dumps(active_plan, indent=2)
        system_instructions += (
            f"\n\n[ACTIVE EXECUTION PLAN]\n"
            f"You MUST strictly coordinate execution according to the active plan boundaries below. Focus entirely on fulfilling the 'next_step_id' action.\n"
            f"CRITICAL: Do NOT provide a final summary, closing thoughts, or standard user-facing answers if there are ANY pending steps remaining in the plan. You MUST continue delegating tasks to the appropriate agents for each step until ALL steps are marked COMPLETED.\n"
            f"CRITICAL REGARDING 'requires_hitl': When a plan step has 'requires_hitl: true', this does NOT mean you should textually ask the user for permission or wait for confirmation. Instead, it indicates the target tool has built-in, automated UI-driven human-in-the-loop verification. You MUST delegate the task to the agent immediately; the underlying graph will automatically pause execution and present the approval card to the user.\n"
            f"{plan_block}"
        )
    
    # Incorporate long-term memory context if existing
    if state.get("retrieved_memories"):
        memory_block = json.dumps(state["retrieved_memories"], indent=2)
        system_instructions += f"\n\n[LONG TERM SEMANTIC CONTEXT]\nRelevant Permanent Facts:\n{memory_block}"
        
    # Incorporate user dynamic geolocation spatial context
    user_loc = state.get("user_preferences", {}).get("location") if state.get("user_preferences") else None
    if user_loc:
        lat = user_loc.get("latitude")
        lon = user_loc.get("longitude")
        if lat is not None and lon is not None:
            system_instructions += f"\n\n[USER SPATIAL CONTEXT]\nThe user has authorized active Geolocation tracking. Current user location:\nCoordinates: {lat}, {lon}\nUse this physical boundary context to automatically resolve implicit local queries (e.g., 'near me', 'here', 'how long to drive to x?') without bothering the user for their current position."

    # Establish optimized messages stack (token budgeted)
    full_messages = [SystemMessage(content=system_instructions)] + recent_messages
    
    # 2. Bind Delegation Tools (Supervisor Routing)
    openai_tool_schemas = get_delegation_tools()
    
    # Load dynamic config overrides from state if provided
    config_overrides = state.get("config_overrides") or {}
    temperature = config_overrides.get("temperature")
    reasoning_effort = config_overrides.get("reasoning_effort")
    model_name = config_overrides.get("model_name")
    session_id = state.get("session_id")
    
    llm = await get_llm(
        model_name=model_name,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
        session_id=session_id
    )
    
    # Bind tools to execution model, enforcing strict sequential execution to match the router architecture
    runnable_llm = llm.bind_tools(openai_tool_schemas, parallel_tool_calls=False)
    
    m_name = getattr(llm, "model_name", getattr(llm, "model", "unknown"))
    logger.info(f"[{node_name}] Invocating LLM generation [Model={m_name}].")

    await emit_telemetry(
        state, 
        TelemetryEventType.LLM_STARTED, 
        node_name=node_name,
        emotion="excited",
        telemetry_label=f"Reasoning via {m_name}"
    )
    
    # Execute LLM reasoning and aggregate tokens
    final_message_chunk = None
    content_accumulator = ""
    
    try:
        # Stream response to broadcast real-time token metrics
        async for chunk in runnable_llm.astream(full_messages):
            if not final_message_chunk:
                final_message_chunk = chunk
            else:
                final_message_chunk += chunk
                
            # Emit content token stream if present
            if chunk.content:
                chunk_text = ""
                if isinstance(chunk.content, str):
                    chunk_text = chunk.content
                elif isinstance(chunk.content, list):
                    for block in chunk.content:
                        if isinstance(block, str):
                            chunk_text += block
                        elif isinstance(block, dict) and "text" in block:
                            chunk_text += block["text"]
                
                if chunk_text:
                    content_accumulator += chunk_text
                    await emit_telemetry(
                        state, 
                        TelemetryEventType.TOKEN_STREAM, 
                        node_name=node_name,
                        payload={"token": chunk_text}
                    )
    except Exception as e:
        logger.error(f"[{node_name}] LLM invocation collapsed: {e}", exc_info=True)
        raise e

    duration_ms = (time.perf_counter() - start_time) * 1000
    
    # Extract precise LangChain usage metadata if present, fallback to estimates
    token_count = 0
    if hasattr(final_message_chunk, "usage_metadata") and final_message_chunk.usage_metadata:
        token_count = final_message_chunk.usage_metadata.get("total_tokens", 0)
    elif hasattr(final_message_chunk, "response_metadata") and final_message_chunk.response_metadata:
        meta = final_message_chunk.response_metadata
        token_count = meta.get("token_usage", {}).get("total_tokens", 0)
        
    # Fallback: rough estimate if streaming didn't populate metadata
    if not token_count:
        token_count = (len(str(full_messages)) + len(content_accumulator)) // 4

    # Record in Budget Manager
    from backend.app.governance.budget import budget_manager
    if session_id:
        budget_manager.record_tokens(session_id, token_count)
        logger.debug(f"[{node_name}] Logged {token_count} consumed tokens to Session={session_id}")

    await emit_telemetry(
        state, 
        TelemetryEventType.LLM_COMPLETED, 
        node_name=node_name,
        payload={
            "tool_calls": [tc["name"] for tc in final_message_chunk.tool_calls] if hasattr(final_message_chunk, "tool_calls") else [],
            "tokens_emitted": token_count
        }
    )
    
    await emit_telemetry(
        state,
        TelemetryEventType.NODE_COMPLETED,
        node_name=node_name,
        duration_ms=duration_ms
    )
    
    # Inject return state updates
    updates = {
        "messages": [final_message_chunk],
        "active_node": node_name,
        "active_tool_calls": final_message_chunk.tool_calls if hasattr(final_message_chunk, "tool_calls") else []
    }
    
    # Post-Generation Plan Advancement for native textual reasoning steps
    has_tool_calls = bool(updates["active_tool_calls"])
    if active_plan and "steps" in active_plan and not has_tool_calls:
        current_step_id = active_plan.get("next_step_id")
        if current_step_id:
            # Safety Guardrail: Only auto-advance if the current step was designed as a text-only resolution.
            # If the planner explicitly mandated a tool (e.g. 'google_docs_create') but the Orchestrator failed 
            # to generate a tool delegation (e.g. due to textual side-tracking), we MUST NOT silently skip it.
            current_step = next((s for s in active_plan.get("steps", []) if s.get("step_id") == current_step_id), None)
            assigned_tool = current_step.get("assigned_tool") if current_step else None
            
            if not assigned_tool:
                from backend.app.resilience.manager import ExecutionResilienceManager
                logger.info(f"[{node_name}] Completed native textual step: {current_step_id}. Advancing plan pointer.")
                
                # Record step success for the textual resolution
                updated_plan = ExecutionResilienceManager.record_step_success(
                    plan=active_plan,
                    step_id=current_step_id,
                    output={"raw_resolution": "Executed via native orchestrator text logic."}
                )
                updates["execution_plan"] = updated_plan
                logger.info(f"[{node_name}] Plan advanced. Next step pointer: {updated_plan.get('next_step_id')}")
            else:
                logger.warning(f"[{node_name}] Orchestrator generated textual response, but step '{current_step_id}' explicitly requires tool: '{assigned_tool}'. Retaining pending state to safeguard execution boundaries.")
    
    if summary_was_updated:
        updates["working_memory_summary"] = updated_summary
        
    return updates
