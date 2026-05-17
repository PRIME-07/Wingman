from typing import Dict, Any, Optional
from backend.app.cognition.hierarchy import CognitiveStateHierarchy
from backend.app.core.logging import logger

class CognitiveRuntimeGate:
    """
    Manages extraction, mutation, validation, and serialization 
    of strict cognitive state layers during node executions.
    """

    @staticmethod
    def get_hierarchy(state: Dict[str, Any]) -> CognitiveStateHierarchy:
        """
        Safely parses the structured hierarchy container from current state dict.
        Automatically falls back to a safe initialization if missing.
        """
        h_data = state.get("cognitive_hierarchy")
        
        if not h_data:
            logger.warning("[Cognition-Gate] Hierarchy missing in active state. Injecting emergency default container.")
            # Fallback constructor
            instance = CognitiveStateHierarchy.initialize_default(
                trace_id=state.get("trace_id", "unknown"),
                run_id=state.get("run_id", "unknown"),
                session_id=state.get("session_id", "unknown"),
                is_background=state.get("is_background", False),
                has_hitl_clearance=state.get("has_hitl_clearance", True)
            )
            return instance
            
        try:
            return CognitiveStateHierarchy.model_validate(h_data)
        except Exception as e:
            logger.error(f"[Cognition-Gate] Severe structural violation parsing state hierarchy: {e}")
            # Resilient fallback
            return CognitiveStateHierarchy.initialize_default(
                trace_id=state.get("trace_id", "unknown"),
                run_id=state.get("run_id", "unknown"),
                session_id=state.get("session_id", "unknown"),
                is_background=state.get("is_background", False),
                has_hitl_clearance=state.get("has_hitl_clearance", True)
            )

    @staticmethod
    def serialize(hierarchy: CognitiveStateHierarchy) -> Dict[str, Any]:
        """Serializes hierarchy instance for LangGraph state update."""
        return hierarchy.model_dump(mode="json")

    @staticmethod
    def sync_global_to_hierarchy(state: Dict[str, Any]) -> CognitiveStateHierarchy:
        """
        Pulls scattered top-level primitive keys into the structured hierarchy container
        to guarantee synchronicity before complex evaluation steps.
        """
        hierarchy = CognitiveRuntimeGate.get_hierarchy(state)
        
        # Sync working
        hierarchy.working.working_memory_summary = state.get("working_memory_summary", "") or ""
        hierarchy.working.document_context = state.get("document_context", []) or []
        hierarchy.working.active_trace_logs = state.get("execution_trace", []) or []
        hierarchy.working.timezone = state.get("timezone", "UTC")
        
        # Sync task
        hierarchy.task.execution_plan = state.get("execution_plan")
        hierarchy.task.active_task_id = state.get("active_task")
        
        # Sync semantic
        hierarchy.semantic.retrieved_memories = state.get("retrieved_memories", []) or []
        
        # Sync reactive
        hierarchy.reactive.active_node = state.get("active_node", "unknown")
        hierarchy.reactive.interrupted = state.get("interrupted", False)
        hierarchy.reactive.selected_tools = state.get("selected_tools", []) or []
        
        return hierarchy
