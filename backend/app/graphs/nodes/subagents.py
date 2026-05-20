import time
import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from backend.app.services.llm.client import get_llm
from backend.app.graphs.state import WingmanState
from backend.app.core.logging import logger
from backend.app.tools.base.interface import ToolExecutionContext
from langchain_core.runnables.config import RunnableConfig

# Connection handles for execution idempotency cache
from backend.app.memory.mongodb_client import mongo_client

# Inject Telemetry capabilities for Subagent Tool Execution
from backend.app.graphs.execution.helpers import emit_telemetry
from backend.app.telemetry.schemas import TelemetryEventType

# Import atomic tools
from backend.app.tools.websearch.tool import WebSearchTool
from backend.app.tools.youtube.tool import YoutubeSearchTool
from backend.app.tools.gmail.tool import GmailDraftTool
from backend.app.tools.slack.tool import SlackDraftTool, SlackChannelListTool
from backend.app.tools.clock.tool import ClockTool
from backend.app.tools.clock.timer_tool import TimerSetTool, TimerCancelTool, TimerListTool
from backend.app.tools.calendar.tool import CalendarScheduleTool, CalendarQueryTool, CalendarModifyTool, CalendarDeleteTool, CalendarBatchScheduleTool, CalendarBatchModifyTool, CalendarBatchDeleteTool
from backend.app.tools.google_docs.tool import DocsCreateTool, DocsReadTool, DocsEditTool, DocsSearchTool
from backend.app.tools.google_sheets.tool import SheetsCreateTool, SheetsReadTool, SheetsAppendTool, SheetsUpdateTool, SheetsSearchTool
from backend.app.tools.google_maps.tool import MapsDirectionsTool, MapsNearbySearchTool
from backend.app.tools.weather.tool import WeatherQueryTool
from backend.app.tools.memory.tool import MemoryRetrievalTool
from backend.app.tools.rag.tool import DocumentRAGTool
from backend.app.tools.contacts.tool import ContactsSearchTool, ContactsCreateTool

# Map tools to specific agents
WEB_TOOLS = [WebSearchTool(), YoutubeSearchTool()]
COMM_TOOLS = [GmailDraftTool(), SlackDraftTool(), SlackChannelListTool(), ContactsSearchTool(), ContactsCreateTool()]
WORK_TOOLS = [
    ClockTool(), TimerSetTool(), TimerCancelTool(), TimerListTool(),
    CalendarScheduleTool(), CalendarBatchScheduleTool(), CalendarBatchModifyTool(), CalendarBatchDeleteTool(), CalendarQueryTool(), CalendarModifyTool(), CalendarDeleteTool(), DocsCreateTool(),
    DocsReadTool(), DocsEditTool(), DocsSearchTool(),
    SheetsCreateTool(), SheetsReadTool(), SheetsAppendTool(), SheetsUpdateTool(), SheetsSearchTool(),
    MapsDirectionsTool(), MapsNearbySearchTool(), WeatherQueryTool(), ContactsSearchTool(), ContactsCreateTool()
]
RAG_TOOLS = [MemoryRetrievalTool(), DocumentRAGTool()]

def _make_serializable(val: Any) -> Any:
    """Recursively dumps Pydantic model objects to dictionary structures for JSON safety."""
    if isinstance(val, dict):
        return {k: _make_serializable(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [_make_serializable(v) for v in val]
    elif hasattr(val, "model_dump") and callable(val.model_dump):
        return _make_serializable(val.model_dump())
    elif hasattr(val, "dict") and callable(val.dict):
        return _make_serializable(val.dict())
    return val

async def execute_subagent(state: WingmanState, agent_name: str, tools: list, prompt: str, config: RunnableConfig = None) -> Dict[str, Any]:
    """Helper to execute a specific sub-agent ReAct loop and return its output as a ToolMessage."""
    start_time = time.perf_counter()
    logger.info(f"[SubAgent] Waking {agent_name}...")
    
    if not state.get("active_tool_calls"):
        return {"messages": []}
        
    tool_call = state["active_tool_calls"][0]
    call_id = tool_call.get("id")
    # Extract query/request from arguments
    args = tool_call.get("args", {})
    query = args.get("query") or args.get("request") or "Please perform the requested action."
    
    # Inject conversational context into the query so the subagent has context of previous conversation.
    memory_summary = state.get("working_memory_summary", "")
    if memory_summary:
        query = f"Task: {query}\n\n[CONVERSATIONAL CONTEXT]\n{memory_summary}"
        
    # Inject dynamic user spatial boundaries to ground local lookups
    user_loc = state.get("user_preferences", {}).get("location") if state.get("user_preferences") else None
    if user_loc:
        lat = user_loc.get("latitude")
        lon = user_loc.get("longitude")
        if lat is not None and lon is not None:
            query = f"{query}\n\n[USER SPATIAL CONTEXT]\nCoordinates: {lat}, {lon}\nYou can feed these coordinates directly to spatial tools (weather, maps) if the task demands local queries."
    
    # Initialize the LLM with dynamic state config
    config_overrides = state.get("config_overrides") or {}
    llm = await get_llm(
        model_name=config_overrides.get("model_name"),
        temperature=config_overrides.get("temperature"),
        reasoning_effort=config_overrides.get("reasoning_effort"),
        session_id=state.get("session_id")
    )
    
    # 1. Initialize variables for multi-pass execution loop (handles bubbled interrupts)
    hitl_decision = None
    invoke_kwargs = {"messages": [("user", query)]}
    
    while True:
        # Track invocation counts strictly WITHIN this specific ReAct session iteration.
        # This provides unique, deterministic sequencing across graph resumptions/replays,
        # preventing collision even if the exact same tool is invoked twice in one prompt lifecycle.
        tool_call_counters = defaultdict(int)
        
        # Convert custom BaseWingmanTool instances to LangChain StructuredTools
        langchain_tools = []
        for w_tool in tools:
            def _make_coro(tool_inst):
                async def _coro(**kwargs: Any) -> str:
                    serializable_kwargs = _make_serializable(kwargs)
                    curr_run_id = state.get("run_id", "gen-run")
                    args_str = json.dumps(serializable_kwargs, sort_keys=True)
                    
                    # Deterministic sequence tracking for cache separation
                    curr_tool_index = tool_call_counters[tool_inst.name]
                    tool_call_counters[tool_inst.name] += 1
                    
                    # Connect global client and establish cache scope
                    mongo_client.connect()
                    cache_coll = mongo_client.db["tool_execution_cache"]
                    
                    cache_query = {
                        "run_id": curr_run_id,
                        "agent_name": agent_name,
                        "tool_name": tool_inst.name,
                        "arguments_hash": args_str,
                        "call_index": curr_tool_index
                    }
                    
                    # A. ATOMIC CACHE READ (Ensures absolute idempotency across HITL parent resumptions)
                    try:
                        cached_entry = await cache_coll.find_one(cache_query)
                        if cached_entry:
                            logger.info(f"[SubAgentCache] CACHE HIT: Skipping execution of '{tool_inst.name}' [{agent_name} / Index={curr_tool_index}].")
                            
                            # Dispatch artificial cache-hit telemetry for seamless UX transparency
                            await emit_telemetry(
                                state,
                                TelemetryEventType.TOOL_STARTED,
                                node_name=agent_name,
                                tool_name=tool_inst.name,
                                payload={"arguments": serializable_kwargs, "cached": True}
                            )
                            await emit_telemetry(
                                state,
                                TelemetryEventType.TOOL_COMPLETED,
                                node_name=agent_name,
                                tool_name=tool_inst.name,
                                payload={
                                    "output_preview": "[CACHED RESULT] " + (str(cached_entry["output"])[:200] if cached_entry.get("output") else ""),
                                    "authenticity": "CACHED"
                                },
                                duration_ms=0.0
                            )
                            return json.dumps(cached_entry["output"])
                    except Exception as e:
                        logger.warning(f"[SubAgentCache] Operation failed to query ledger: {e}")
 
                    # B. FRESH TOOL EXECUTION
                    ctx = ToolExecutionContext(
                        trace_id=state.get("trace_id", "gen-trace"),
                        run_id=curr_run_id,
                        user_timezone=state.get("timezone", "UTC"),
                        is_background=state.get("is_background", False),
                        has_hitl_clearance=state.get("has_hitl_clearance", False),
                        hitl_decision=hitl_decision,  # Inject any pre-approved decision
                        metadata={
                            "session_id": state.get("session_id"),
                            "location": state.get("user_preferences", {}).get("location") if state.get("user_preferences") else None
                        }
                    )
                    await emit_telemetry(
                        state,
                        TelemetryEventType.TOOL_STARTED,
                        node_name=agent_name,
                        tool_name=tool_inst.name,
                        payload={"arguments": serializable_kwargs}
                    )
                    
                    tool_start_time = time.perf_counter()
                    
                    # Execute actual integration client (may raise GraphInterrupt and suspend process)
                    result = await tool_inst.run(serializable_kwargs, ctx)
                    
                    duration_ms = (time.perf_counter() - tool_start_time) * 1000.0
                    
                    if result.success:
                        # C. ATOMIC CACHE WRITE (Safeguard side-effects from replay amplification)
                        try:
                            await cache_coll.insert_one({
                                **cache_query,
                                "session_id": state.get("session_id", "gen-session"),
                                "output": result.output,
                                "timestamp": datetime.utcnow()
                            })
                            logger.info(f"[SubAgentCache] Successfully cached tool output for '{tool_inst.name}' [Index={curr_tool_index}].")
                        except Exception as e:
                            logger.error(f"[SubAgentCache] Failure registering operation ledger: {e}")
                            
                        await emit_telemetry(
                            state,
                            TelemetryEventType.TOOL_COMPLETED,
                            node_name=agent_name,
                            tool_name=tool_inst.name,
                            payload={
                                "output_preview": str(result.output)[:200] if result.output else "",
                                "authenticity": result.authenticity
                            },
                            duration_ms=duration_ms
                        )
                        return json.dumps(result.output)
                    else:
                        await emit_telemetry(
                            state,
                            TelemetryEventType.TOOL_FAILED,
                            node_name=agent_name,
                            tool_name=tool_inst.name,
                            payload={"error": result.error},
                            duration_ms=duration_ms
                        )
                        return f"Error during execution: {result.error}"
                return _coro

            lc_tool = StructuredTool.from_function(
                func=None,
                coroutine=_make_coro(w_tool),
                name=w_tool.name,
                description=w_tool.description,
                args_schema=w_tool.args_schema
            )
            langchain_tools.append(lc_tool)

        # Create the ReAct loop graph for this agent execution pass
        agent_executor = create_react_agent(llm, tools=langchain_tools, prompt=prompt)
        
        # Run the agent synchronously wrapped in await
        if config:
            result = await agent_executor.ainvoke(invoke_kwargs, config=config)
        else:
            result = await agent_executor.ainvoke(invoke_kwargs)
        
        # 2. Check if the execution hit an internal LangGraph interrupt
        if "__interrupt__" in result and result["__interrupt__"]:
            interrupt_info = result["__interrupt__"][0]
            logger.info(f"[SubAgent] Intercepted subagent interrupt for {agent_name}. Bubbling UP to outer orchestrator loop.")
            
            # Trigger real LangGraph interrupt at the parent graph level. 
            # Execution suspends here; when it resumes, it receives the decision object.
            from langgraph.types import interrupt as lg_interrupt
            hitl_decision = lg_interrupt(interrupt_info.value)
            
            logger.info(f"[SubAgent] Resumed {agent_name} execution with provided decision: {hitl_decision}")
            # Iterate again to execute the tool with pre-loaded credentials
            continue
        else:
            # Completed successfully without additional suspension
            break

    # Extract final output from agent
    final_output = result["messages"][-1].content
    
    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"[SubAgent] {agent_name} finished task in {duration_ms:.2f}ms.")
    
    # 3. Post-Execution Plan State Advancement
    updated_plan = state.get("execution_plan")
    if updated_plan and "steps" in updated_plan:
        from backend.app.resilience.manager import ExecutionResilienceManager
        
        current_step_id = updated_plan.get("next_step_id")
        last_out = {"result": final_output}
        
        updated_plan = ExecutionResilienceManager.record_step_success(
            plan=updated_plan,
            step_id=current_step_id,
            output=last_out
        )
        logger.info(
            f"[SubAgent] Plan step completed successfully. Next: {updated_plan.get('next_step_id')}"
        )
    
    # Package response back to the orchestrator as a ToolMessage
    return_state = {
        "messages": [ToolMessage(content=final_output, tool_call_id=call_id)],
        "active_node": agent_name,
        "active_tool_calls": [] # Clear active call
    }
    
    if updated_plan:
        return_state["execution_plan"] = updated_plan
        
    return return_state

async def web_agent_node(state: WingmanState, config: RunnableConfig) -> Dict[str, Any]:
    prompt = (
        "You are the Web Research Agent. Execute search tools to find accurate, up-to-date information and summarize the results clearly.\n"
        "REGIONAL SEARCH GUIDELINE: The system environment defaults to India. Unless the user explicitly specifies another country, "
        "ALWAYS formulate your web search queries to cater to India (e.g., looking for Indian retailers, availability in India, or pricing in INR) "
        "and interpret/summarize search results focusing on Indian relevance and Indian Rupee (₹) equivalent conversions."
    )
    return await execute_subagent(state, "web_agent", WEB_TOOLS, prompt, config)

async def comm_agent_node(state: WingmanState, config: RunnableConfig) -> Dict[str, Any]:
    prompt = (
        "You are the Communication Agent. Handle email drafting and Slack messaging precisely as requested.\n"
        "PERSONALIZATION GUIDELINE: This is an exclusive single-user environment. The user's name is 'Anuj Mankumare'. "
        "When writing emails or crafting communications, ALWAYS sign off as 'Anuj Mankumare' (or 'Anuj' if informal), and NEVER leave general placeholders like '[Your Name]' or '[User]'.\n"
        "SLACK DESTINATION VERIFICATION: If the user requests a Slack message but does not explicitly name the destination "
        "(e.g. a specific channel or 'DM me'), you MUST FIRST ask the user to confirm where they would like it sent "
        "(e.g. in a specific channel name or as a Direct Message) rather than guessing the target.\n"
        "REGIONAL GUIDELINE: Format all monetary sums (Rupees/₹), physical dimensions (Metric), and large numeric values "
        "(Indian Number System - Lakhs and Crores) aligned to Indian regional standards.\n"
        "CRITICAL SAFETY PROTOCOL: Never textually ask the user for permission before executing a tool! All write tools (Gmail, Slack, etc.) have built-in, automated UI-driven confirmation screens. Simply call the tool immediately; the system handles interactive approval automatically."
    )
    return await execute_subagent(state, "comm_agent", COMM_TOOLS, prompt, config)

async def work_agent_node(state: WingmanState, config: RunnableConfig) -> Dict[str, Any]:
    prompt = (
        "You are the Workspace Agent. Manage calendars, documents, timers, and spatial/weather data effectively. "
        "When creating documents, spreadsheets, or scheduled items, you MUST explicitly confirm successful creation "
        "and provide a clear, clickable Markdown link to the resource using the exact URL returned by the tool.\n"
        "REGIONAL GUIDELINE: Present and format all metrics using Metric units (e.g., Kilograms, Meters, Celsius), monetary references in Indian Rupees (₹), "
        "and large numerical representations using the Indian Number System (Lakhs/Crores).\n"
        "TIMER GUIDELINE: When setting, starting, or cancelling countdown timers, NEVER output or display the internal UUID string (e.g., `timer_id`) in your final conversational response to the user. Simply confirm that the timer has been successfully started or cancelled, as the frontend's Live Activities bar automatically renders and displays the live countdown details for the user.\n"
        "CRITICAL SAFETY PROTOCOL: Never textually ask the user for permission or authorization before executing a write-action tool (e.g. editing a doc, updating a spreadsheet, or booking a calendar event). All system write tools possess integrated, automated UI-driven HITL approval gates. Simply invoke the tool immediately when requested; the platform automatically manages interactive user approvals.\n"
        "CRITICAL FOR MAPS: When providing navigation, driving directions, or route estimates, you MUST proactively "
        "extract the 'navigation_url' from the tool result and present it as a clear, clickable Markdown link "
        "styled as '[👉 Open in Google Maps](URL)' so the user can launch live GPS immediately."
    )
    return await execute_subagent(state, "work_agent", WORK_TOOLS, prompt, config)

async def rag_agent_node(state: WingmanState, config: RunnableConfig) -> Dict[str, Any]:
    prompt = "You are the Knowledge Agent. Retrieve documents and semantic memory facts to answer the user's query."
    return await execute_subagent(state, "rag_agent", RAG_TOOLS, prompt, config)
