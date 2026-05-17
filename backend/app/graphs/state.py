from typing import Annotated, Sequence, TypedDict, Dict, Any, List, Optional
from datetime import datetime
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class WingmanState(TypedDict):
    """
    Global state schema for the Wingman Agent Orchestration framework.
    Designed for rich multi-step memory retrieval, telemetry observability,
    and flexible Human-in-the-Loop interrupt handling.
    """
    
    # Conversational Message Chain (automatically merged by add_messages)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Active task details being handled by the agent
    active_task: Optional[str]
    
    # Semantic memories retrieved from Neo4j Graph DB
    retrieved_memories: List[Dict[str, Any]]
    
    # RAG chunks injected from VectorDB (Pinecone)
    document_context: List[Dict[str, Any]]
    
    # Tools selected by routing logic for execution
    selected_tools: List[Dict[str, Any]]
    
    # Live performance and trace log history of execution cycles
    execution_trace: List[Dict[str, Any]]
    
    # Latest telemetry logs to broadcast
    telemetry_events: List[Dict[str, Any]]
    
    # System details for pending action authorization (HITL)
    pending_approvals: List[Dict[str, Any]]
    
    # Session & Runtime Isolation
    session_id: Optional[str]
    
    # Rolling Context & Cognitive Compression
    working_memory_summary: Optional[str]
    
    # Planner / Executor architecture state
    execution_plan: Optional[Dict[str, Any]]
    
    # Cognitive Loop Reflection outcomes
    reflection_notes: Optional[Dict[str, Any]]
    
    # Execution engine tracking state
    active_node: str
    interrupted: bool
    
    # Client/User context defaults
    timezone: str
    user_preferences: Dict[str, Any]
    
    # Trace identification
    trace_id: str
    run_id: str
    
    # Dynamic runtime configuration
    reasoning_metadata: Dict[str, Any]
    streaming_metadata: Dict[str, Any]
    
    # Captured final output
    final_response: Optional[str]
    
    # Timestamp recordings
    started_at: datetime
    updated_at: datetime
    
    # Security & Interactive Context
    is_background: bool
    has_hitl_clearance: bool
    
    # P1 Cognitive State Hierarchy Boundary Tracking
    cognitive_hierarchy: Optional[Dict[str, Any]]
    
    # Operational Stabilization Metrics
    execution_authenticity_ledger: List[Dict[str, Any]]
    global_confidence_score: float
    
    # Priority and Execution Scheduling
    priority_tier: str # e.g., "CRITICAL", "HIGH", "MEDIUM", "LOW", "BACKGROUND"
    
    # Dynamic Generation Overrides (mapped from UI reasoning/model selectors)
    config_overrides: Optional[Dict[str, Any]]
    
    # Dispatch queue holding tool calls output by the Orchestrator awaiting execution
    active_tool_calls: List[Dict[str, Any]]




