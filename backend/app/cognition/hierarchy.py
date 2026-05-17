from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from langchain_core.messages import BaseMessage

class ReactiveState(BaseModel):
    """
    Short-lived ephemeral state driving immediate action.
    Flushed or overridden frequently during runtime execution steps.
    """
    active_node: str = Field(default="init")
    selected_tools: List[Dict[str, Any]] = Field(default_factory=list)
    streaming_token_chunk: Optional[str] = None
    interrupted: bool = False
    pending_approvals: List[Dict[str, Any]] = Field(default_factory=list)

class WorkingState(BaseModel):
    """
    Active reasoning context required for immediate problem solving.
    Contains current conversation window and retrieved RAG context.
    """
    working_memory_summary: str = ""
    document_context: List[Dict[str, Any]] = Field(default_factory=list)
    active_trace_logs: List[Dict[str, Any]] = Field(default_factory=list)
    timezone: str = "UTC"

class TaskState(BaseModel):
    """
    The planner/executor boundary containing structured goals and execution steps.
    Prevents planner assumptions from leaking directly into facts.
    """
    active_task_id: Optional[str] = None
    execution_plan: Optional[Dict[str, Any]] = None
    plan_status: str = "idle" # idle | executing | compensating | success | failed
    rollback_manifest: List[str] = Field(default_factory=list)

class SessionState(BaseModel):
    """
    Session-level isolation parameters. Defines the session identity and lifecycle constraints.
    """
    session_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    session_name: str = "New Session"
    name_confidence: float = 0.0 # Provisional tracking

class SemanticState(BaseModel):
    """
    Permanent or long-term knowledge assets. Strictly gated.
    No content should enter Neo4j without passing through here AND getting validation flags.
    """
    retrieved_memories: List[Dict[str, Any]] = Field(default_factory=list)
    verified_candidates: List[Dict[str, Any]] = Field(default_factory=list) # Gated pending commit
    commited_memories: List[Dict[str, Any]] = Field(default_factory=list)

class SystemMetaState(BaseModel):
    """
    Infrastructure level security and capability parameters.
    """
    trace_id: str
    run_id: str
    is_background: bool = False
    has_hitl_clearance: bool = True
    config_overrides: Dict[str, Any] = Field(default_factory=dict)
    inference_cost_estimate: float = 0.0 # Tracking cost

class CognitiveStateHierarchy(BaseModel):
    """
    Comprehensive isolated multi-layered runtime state container.
    Guarantees data isolation and validates state boundaries before persistence.
    """
    reactive: ReactiveState
    working: WorkingState
    task: TaskState
    session: SessionState
    semantic: SemanticState
    system: SystemMetaState
    
    class Config:
        arbitrary_types_allowed = True

    def validate_memory_commit(self, memory_candidate: Dict[str, Any]) -> bool:
        """
        Strict commit verification gate. 
        Checks confidence scoring, source evidence, and Category boundaries before allowing commit.
        """
        from backend.app.cognition.schemas import MemoryCategory
        
        category = memory_candidate.get("category", MemoryCategory.FACT)
        score = memory_candidate.get("confidence_score", 0.0)
        evidence = memory_candidate.get("evidence") or memory_candidate.get("fact")
        
        # Priority 12: Knowledge Boundary Layer enforcement
        # Blocks speculative and temporal categories from permanent long-term contamination
        if category in [MemoryCategory.ASSUMPTION, MemoryCategory.HYPOTHESIS, MemoryCategory.CONTEXT]:
            # Logged internally at the caller layer to preserve visibility
            return False
            
        # Priority 1/2 Guard: Deny if not verified
        if score < 0.8:
            return False
        if not evidence or len(str(evidence).strip()) < 10:
            return False
            
        return True

    @classmethod
    def initialize_default(cls, trace_id: str, run_id: str, session_id: str, is_background: bool = False, has_hitl_clearance: bool = True):
        """Creates a clean, isolated initial state hierarchy."""
        return cls(
            reactive=ReactiveState(),
            working=WorkingState(),
            task=TaskState(),
            session=SessionState(session_id=session_id),
            semantic=SemanticState(),
            system=SystemMetaState(
                trace_id=trace_id,
                run_id=run_id,
                is_background=is_background,
                has_hitl_clearance=has_hitl_clearance
            )
        )
