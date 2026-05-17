import time
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from backend.app.graphs.state import WingmanState
from backend.app.graphs.execution.helpers import emit_telemetry
from backend.app.telemetry.schemas import TelemetryEventType
from backend.app.planner.schemas import ExecutionPlan
from backend.app.services.llm.client import get_llm
from backend.app.tools.registry import tool_registry
from backend.app.prompts.registry import prompt_registry
from backend.app.core.logging import logger
from backend.app.core.utils import extract_text_content

async def planner_node(state: WingmanState) -> Dict[str, Any]:
    """
    Cognitive Task decomposition step. Resolves user prompt intent into a structured
    multi-step PlanStep roadmap mapped to registry tooling capabilities.
    """
    start_time = time.perf_counter()
    node_name = "planner"
    
    await emit_telemetry(
        state, 
        TelemetryEventType.NODE_STARTED, 
        node_name=node_name,
        emotion="thinking",
        telemetry_label="Planning Execution Steps"
    )
    
    # If we already have an active plan and it isn't finished, skip re-planning
    # unless we expressly decide to re-plan in dynamic routing logic.
    existing_plan = state.get("execution_plan")
    if existing_plan and not existing_plan.get("is_complete", False):
        logger.info(f"[{node_name}] Active plan detected. Resuming execution of existing steps.")
        duration_ms = (time.perf_counter() - start_time) * 1000
        await emit_telemetry(state, TelemetryEventType.NODE_COMPLETED, node_name=node_name, duration_ms=duration_ms)
        return {"active_node": node_name}

    # Get latest message content as active goal
    last_message = extract_text_content(state["messages"][-1].content) if state["messages"] else ""
    if not last_message:
        logger.warning(f"[{node_name}] Empty conversation log. Aborting plan compilation.")
        return {"active_node": node_name}

    logger.info(f"[{node_name}] Compiling Execution Plan for: '{last_message[:60]}'")
    
    # Dynamic Capability Discovery & Latency Profiling Audits
    from backend.app.capabilities.checker import capability_discovery
    from backend.app.latency.tracker import latency_tracker
    
    caps = await capability_discovery.discover_capabilities()
    latency_map = await latency_tracker.get_all_latencies()
    
    # Fetch available system tools schema
    tool_definitions = tool_registry.get_openai_tool_definitions()
    
    # Build highly enriched list of tools containing real-time runtime capability signals
    summaries = []
    for t in tool_definitions:
        t_name = t['function']['name']
        desc = t['function'].get('description', '')
        cap = caps.get(t_name)
        
        avg_lat = latency_map.get(t_name)
        latency_text = f"{int(avg_lat)}ms" if avg_lat is not None else "Unknown"
        
        cap_text = "Available: TRUE"
        if cap:
            cap_text = f"Available: {str(cap.available).upper()} [Auth={str(cap.authenticated).upper()}, Reachable={str(cap.provider_reachable).upper()}]"
            if not cap.available:
                cap_text += f" (BLOCKED Reason: {cap.reason})"
        
        summaries.append(f"- {t_name}: {desc}\n  * Runtime {cap_text} | Est. Latency: {latency_text}")
        
    tool_list_summary = "\n".join(summaries)

    
    # Fetch list of uploaded documents from MongoDB to give the planner system vault awareness
    from backend.app.memory.mongodb_client import mongo_client
    docs_summary = "None (No documents currently uploaded to the vault)"
    try:
        uploaded_docs = await mongo_client.list_documents()
        if uploaded_docs:
            doc_summaries = []
            for d in uploaded_docs:
                file_size_kb = round(d.get("file_size", 0) / 1024, 1)
                doc_summaries.append(
                    f"- File Name: '{d['filename']}' | Document ID: '{d['doc_id']}' | Chunks: {d.get('chunk_count', 0)}"
                )
            docs_summary = "\n".join(doc_summaries)
    except Exception as ex:
        logger.error(f"[{node_name}] Failed retrieving documents for planner context: {ex}")
        docs_summary = "Error reading vault inventory catalog."

    config_overrides = state.get("config_overrides") or {}
    model_name = config_overrides.get("model_name")
    reasoning_effort = config_overrides.get("reasoning_effort")
    session_id = state.get("session_id")
    
    llm = await get_llm(
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        temperature=0.2,
        session_id=session_id
    )
    structured_llm = llm.with_structured_output(ExecutionPlan, strict=True)
    from langchain_core.messages import SystemMessage
    from backend.app.cognition.working_memory import working_memory_compiler
    
    # 1. Compile optimized message context stack to support multi-turn disambiguation
    current_summary = state.get("working_memory_summary", "")
    recent_messages, _, _ = await working_memory_compiler.compile_and_budget(
        messages=state["messages"],
        current_summary=current_summary
    )
    
    planner_base = prompt_registry.get_prompt("planner_instruction")
    planner_system_content = (
        "You generate rigid JSON execution plans mapping objectives to dependency graphs.\n\n" +
        planner_base.format(tool_list_summary=tool_list_summary, docs_summary=docs_summary) +
        "\n\n[CRITICAL INSTRUCTION]\nEvaluate the chronological conversation history below. Determine the ultimate high-level user goal in context, disambiguate short statements or updates using previous turns.\n" +
        "CRITICAL CONTEXT AUDIT: Analyze the last 50 turns of chat. If they contain sufficient information, proceed natively. If the query requests user preferences, historical project details, or long-term facts NOT present in this recent local history, you MUST explicitly plan a preliminary step to invoke the 'memory_retrieval' or 'document_rag' tools to pull the missing context from Neo4j/Pinecone before concluding."
    )
    
    full_messages = [SystemMessage(content=planner_system_content)] + recent_messages
    
    try:
        generated_plan: ExecutionPlan = await structured_llm.ainvoke(full_messages)
        
        # Update the first step marker if it was omitted
        if generated_plan.steps and not generated_plan.next_step_id:
            generated_plan.next_step_id = generated_plan.steps[0].step_id
            
        plan_dump = generated_plan.model_dump()
        logger.info(f"[{node_name}] Compiled Plan successfully with {len(generated_plan.steps)} steps.")
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        await emit_telemetry(
            state, 
            TelemetryEventType.NODE_COMPLETED, 
            node_name=node_name, 
            duration_ms=duration_ms,
            payload={"step_count": len(generated_plan.steps)}
        )
        
        return {
            "execution_plan": plan_dump,
            "active_node": node_name
        }
    except Exception as e:
        logger.error(f"[{node_name}] Plan compilation failed: {e}", exc_info=True)
        # Fallback gracefully to single direct step
        fallback_plan = {
            "goal": last_message,
            "complexity": "low",
            "steps": [
                {
                    "step_id": "fallback-1",
                    "description": "Process user query directly",
                    "assigned_tool": None,
                    "dependencies": [],
                    "requires_hitl": False,
                    "status": "pending"
                }
            ],
            "next_step_id": "fallback-1",
            "is_complete": False
        }
        return {
            "execution_plan": fallback_plan,
            "active_node": node_name
        }
