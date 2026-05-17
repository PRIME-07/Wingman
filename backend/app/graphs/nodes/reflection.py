import time
import json
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from backend.app.graphs.state import WingmanState
from backend.app.graphs.execution.helpers import emit_telemetry
from backend.app.telemetry.schemas import TelemetryEventType
from backend.app.cognition.schemas import ReflectionOutcome, MemoryCategory
from backend.app.services.llm.client import get_llm
from backend.app.memory.neo4j_client import neo4j_client
from backend.app.prompts.registry import prompt_registry
from backend.app.core.logging import logger
from backend.app.core.utils import extract_text_content
from backend.app.governance.budget import budget_manager
from backend.app.cognition.runtime_gate import CognitiveRuntimeGate
from backend.app.verification.verifier import MemoryGroundingVerifier
from backend.app.provenance.models import MemoryProvenance

async def reflection_node(state: WingmanState) -> Dict[str, Any]:
    """
    Self-Critique and Memory Extraction step. Inspects the execution log, assigns
    a quality evaluation score, distills meaningful insights for permanent Neo4j storage,
    and synthesizes final coherent AIMessage.
    """
    start_time = time.perf_counter()
    node_name = "reflection"
    
    await emit_telemetry(state, TelemetryEventType.NODE_STARTED, node_name=node_name)
    
    # Format current execution context
    chat_history = []
    for msg in state["messages"]:
        role = "system" if msg.type == "system" else "user" if msg.type == "human" else "ai" if msg.type == "ai" else "tool"
        text_content = extract_text_content(msg.content)
        chat_history.append(f"[{role.upper()}] {text_content[:500]}")
    
    history_block = "\n".join(chat_history)
    
    plan_block = "No execution plan was run."
    if state.get("execution_plan"):
        plan_block = json.dumps(state["execution_plan"], indent=2)
        
    config_overrides = state.get("config_overrides") or {}
    model_name = config_overrides.get("model_name")
    reasoning_effort = config_overrides.get("reasoning_effort")
    session_id = state.get("session_id")
    
    llm = await get_llm(
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        temperature=0.1, 
        session_id=session_id
    ) # High precision evaluation
    structured_llm = llm.with_structured_output(ReflectionOutcome, strict=True)
    
    reflection_base = prompt_registry.get_prompt("reflection_critique")
    reflection_prompt = f"[EXECUTION LOG]\n{history_block}\n\n[FINAL STATE OF PLAN]\n{plan_block}\n\n" + reflection_base
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an objective self-auditing cognitive sub-routine."),
        ("human", "{reflection_prompt}")
    ])
    
    try:
        logger.info(f"[{node_name}] Auditing system execution performance...")
        chain = prompt_template | structured_llm
        reflection: ReflectionOutcome = await chain.ainvoke({"reflection_prompt": reflection_prompt})
        
        # P9 Record approximate token usage for the non-message critique response
        if session_id:
            critique_estimate = (len(reflection_prompt) // 4) + 400 # Input + static buffer for output dict
            budget_manager.record_tokens(session_id, critique_estimate)
            logger.debug(f"[{node_name}] Logged {critique_estimate} est. critique tokens to Session={session_id}")
        
        # 1. Log Critique Analytics to Telemetry
        duration_ms = (time.perf_counter() - start_time) * 1000
        await emit_telemetry(
            state,
            TelemetryEventType.NODE_COMPLETED,
            node_name=node_name,
            duration_ms=duration_ms,
            payload={
                "score": reflection.score,
                "goal_achieved": reflection.goal_achieved,
                "memory_candidates_count": len(reflection.suggested_memories)
            }
        )
        
        # 2. P1-P3: Filter, Audit, & Permanently Anchor High-Quality Memories
        # Extract strict active boundary snapshot
        hierarchy = CognitiveRuntimeGate.sync_global_to_hierarchy(state)
        verifier = MemoryGroundingVerifier()
        
        verified_memories = []
        verification_logs = []
        
        # Strict pre-filter threshold
        candidates = [c for c in reflection.suggested_memories if c.importance_score >= 0.6]
        
        for candidate in candidates:
            logger.info(f"[{node_name}] Routing memory candidate '{candidate.entity}' to anti-hallucination gateway...")
            # Step 2: Run strict grounding verification against the direct execution history
            audit = await verifier.verify_candidate(
                candidate=candidate.model_dump(), 
                execution_trace=chat_history
            )
            
            # Step 1 Guard: Only allow if both NLI verification passed and final hierarchy rules met
            candidate_dict = candidate.model_dump()
            if audit.verified:
                # Adjust confidence based on grounding auditor
                candidate_dict["confidence_score"] = min(candidate.confidence_score, audit.confidence_adjustment)
                
                # Final structural constraint check on the hierarchy object
                cat = candidate_dict.get("category", MemoryCategory.FACT)
                
                if hierarchy.validate_memory_commit(candidate_dict):
                    verified_memories.append(candidate_dict)
                    verification_logs.append(audit.justification)
                    logger.info(f"[{node_name}] Memory PASSED rigorous verification. Staged for commit.")
                elif cat in {MemoryCategory.ASSUMPTION, MemoryCategory.HYPOTHESIS, MemoryCategory.CONTEXT}:
                    logger.warning(f"[{node_name}] Memory BLOCKED by Knowledge Boundary Layer: Speculative/Ephemeral class '{cat}' excluded from Neo4j.")
                else:
                    logger.warning(f"[{node_name}] Memory REJECTED: Confidence threshold ({candidate_dict.get('confidence_score')}) or structural density check failed.")
            else:
                logger.warning(f"[{node_name}] Memory REJECTED by anti-hallucination gate: {audit.justification}")

        if verified_memories:
            logger.info(f"[{node_name}] Persisting {len(verified_memories)} fully-audited semantic facts with active provenance tracking.")
            
            # Setup strict transactional lineage metadata
            provenance = MemoryProvenance(
                session_id=state.get("session_id", "unknown"),
                trace_id=state.get("trace_id", "unknown"),
                run_id=state.get("run_id", "unknown"),
                agent_node=node_name,
                verification_justification="; ".join(verification_logs)[:1000]
            )
            
            # Push into the hierarchy's semantic tracker prior to write
            hierarchy.semantic.verified_candidates.extend(verified_memories)
            
            # Execute graph transaction
            archival_success = neo4j_client.save_semantic_memories(
                verified_memories, 
                provenance=provenance.model_dump(mode="json")
            )
            
            if archival_success:
                logger.info(f"[{node_name}] Hardened memory archival transaction succeeded.")
                hierarchy.semantic.commited_memories.extend(verified_memories)
            else:
                logger.error(f"[{node_name}] Severe graph error: Hardened memory archival transaction failed on Neo4j.")
        
        # Stage sanitized memory container into state response
        hierarchy.semantic.verified_candidates = [] # Flush transients
        serialized_hierarchy = CognitiveRuntimeGate.serialize(hierarchy)
                
        # 3. Pure Optimization: Persona Synthesis completely removed!
        # The Orchestrator's raw AIMessage output is now passed directly to the user.
        # This saves ~1.5s latency and halves token usage per turn.
        
        return {
            "reflection_notes": reflection.model_dump(),
            "active_node": node_name,
            "cognitive_hierarchy": serialized_hierarchy
        }
        
    except Exception as e:
        logger.error(f"[{node_name}] Reflection loop failed: {e}", exc_info=True)
        # Fallback gracefully to prevent loop stall
        fallback_response = AIMessage(content="I have compiled the execution steps. Let me know if you need further modifications.")
        
        # Even on failure, push the default or degraded hierarchy state to avoid breaking schema downstream
        fallback_hierarchy = CognitiveRuntimeGate.get_hierarchy(state)
        fallback_hierarchy.reactive.active_node = node_name
        
        return {
            "messages": [fallback_response],
            "active_node": node_name,
            "cognitive_hierarchy": CognitiveRuntimeGate.serialize(fallback_hierarchy)
        }
