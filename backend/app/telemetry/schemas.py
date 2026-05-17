from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class TelemetryEventType(str, Enum):
    GRAPH_STARTED = "graph_started"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    TOOL_SELECTED = "tool_selected"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    LLM_STARTED = "llm_started"
    LLM_COMPLETED = "llm_completed"
    MEMORY_RETRIEVED = "memory_retrieved"
    HITL_REQUESTED = "hitl_requested"
    HITL_RESOLVED = "hitl_resolved"
    GRAPH_COMPLETED = "graph_completed"
    GRAPH_FAILED = "graph_failed"
    TOKEN_STREAM = "token_stream" # Token-by-token chunk emissions
    EMOTION_UPDATE = "emotion_update" # Targeted emotional state shifts
    DOC_INGEST_PROGRESS = "doc_ingest_progress" # Real-time ingestion tracking
    
    # Spatial Intelligence Trace Hooks
    SPATIAL_RESOLVED = "spatial_resolved"
    ROUTING_CALCULATED = "routing_calculated"
    NEARBY_SEARCHED = "nearby_searched"
    
    # Slack DM and User Resolution Tracking
    SLACK_USER_RESOLVED = "slack_user_resolved"
    SLACK_DM_OPENED = "slack_dm_opened"
    SLACK_DM_CACHE_HIT = "slack_dm_cache_hit"
    SLACK_DM_SENT = "slack_dm_sent"

class TelemetryDurabilityTier(str, Enum):
    TRANSIENT = "transient"   # WebSocket streaming ONLY, never saved (e.g. heartbeats, token chunks)
    SESSION = "session"       # Saved to Mongo session log, pruned during nightly consolidations
    DURABLE = "durable"       # Saved to immutable MongoDB long-term operational audit tables
    PERMANENT = "permanent"   # Commited permanently to semantic graph stores (Neo4j)

class TelemetryUXLevel(str, Enum):
    SIMPLE = "simple"         # Standard minimal user-facing notification (e.g., "Wingman is typing...")
    ADVANCED = "advanced"     # High-level functional milestones (e.g., "Running plan step 2: email_sender")
    DEVELOPER = "developer"   # Verbose tracing, raw state dicts, performance metrics

# Static mapper from event classification to suggested frontend exposure levels
UX_LEVEL_MAP = {
    TelemetryEventType.GRAPH_STARTED: TelemetryUXLevel.SIMPLE,
    TelemetryEventType.GRAPH_COMPLETED: TelemetryUXLevel.SIMPLE,
    TelemetryEventType.GRAPH_FAILED: TelemetryUXLevel.SIMPLE,
    TelemetryEventType.HITL_REQUESTED: TelemetryUXLevel.SIMPLE,
    TelemetryEventType.HITL_RESOLVED: TelemetryUXLevel.SIMPLE,
    TelemetryEventType.TOKEN_STREAM: TelemetryUXLevel.SIMPLE,
    TelemetryEventType.EMOTION_UPDATE: TelemetryUXLevel.SIMPLE,
    TelemetryEventType.DOC_INGEST_PROGRESS: TelemetryUXLevel.SIMPLE,
    
    TelemetryEventType.TOOL_SELECTED: TelemetryUXLevel.ADVANCED,
    TelemetryEventType.TOOL_COMPLETED: TelemetryUXLevel.ADVANCED,
    TelemetryEventType.TOOL_FAILED: TelemetryUXLevel.ADVANCED,
    TelemetryEventType.MEMORY_RETRIEVED: TelemetryUXLevel.ADVANCED,
    TelemetryEventType.SPATIAL_RESOLVED: TelemetryUXLevel.ADVANCED,
    TelemetryEventType.ROUTING_CALCULATED: TelemetryUXLevel.ADVANCED,
    TelemetryEventType.NEARBY_SEARCHED: TelemetryUXLevel.ADVANCED,
    
    TelemetryEventType.NODE_STARTED: TelemetryUXLevel.DEVELOPER,
    TelemetryEventType.NODE_COMPLETED: TelemetryUXLevel.DEVELOPER,
    TelemetryEventType.TOOL_STARTED: TelemetryUXLevel.DEVELOPER,
    TelemetryEventType.LLM_STARTED: TelemetryUXLevel.DEVELOPER,
    TelemetryEventType.LLM_COMPLETED: TelemetryUXLevel.DEVELOPER,
    
    # Developer Tracing Only
    TelemetryEventType.SLACK_USER_RESOLVED: TelemetryUXLevel.DEVELOPER,
    TelemetryEventType.SLACK_DM_OPENED: TelemetryUXLevel.DEVELOPER,
    TelemetryEventType.SLACK_DM_CACHE_HIT: TelemetryUXLevel.DEVELOPER,
    TelemetryEventType.SLACK_DM_SENT: TelemetryUXLevel.DEVELOPER
}

# Static mapper defining absolute persistence lifespans for audit governance
DURABILITY_MAP = {
    TelemetryEventType.TOKEN_STREAM: TelemetryDurabilityTier.TRANSIENT,
    TelemetryEventType.NODE_STARTED: TelemetryDurabilityTier.TRANSIENT,
    TelemetryEventType.NODE_COMPLETED: TelemetryDurabilityTier.TRANSIENT,
    TelemetryEventType.LLM_STARTED: TelemetryDurabilityTier.TRANSIENT,
    TelemetryEventType.LLM_COMPLETED: TelemetryDurabilityTier.TRANSIENT,
    TelemetryEventType.EMOTION_UPDATE: TelemetryDurabilityTier.TRANSIENT,
    TelemetryEventType.DOC_INGEST_PROGRESS: TelemetryDurabilityTier.TRANSIENT,
    
    TelemetryEventType.TOOL_STARTED: TelemetryDurabilityTier.SESSION,
    TelemetryEventType.TOOL_SELECTED: TelemetryDurabilityTier.SESSION,
    TelemetryEventType.MEMORY_RETRIEVED: TelemetryDurabilityTier.SESSION,
    
    TelemetryEventType.TOOL_COMPLETED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.TOOL_FAILED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.HITL_REQUESTED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.HITL_RESOLVED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.SLACK_USER_RESOLVED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.SLACK_DM_OPENED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.SLACK_DM_CACHE_HIT: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.SLACK_DM_SENT: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.GRAPH_STARTED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.GRAPH_COMPLETED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.GRAPH_FAILED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.SPATIAL_RESOLVED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.ROUTING_CALCULATED: TelemetryDurabilityTier.DURABLE,
    TelemetryEventType.NEARBY_SEARCHED: TelemetryDurabilityTier.DURABLE,
}

class TelemetryEvent(BaseModel):
    """
    Strict, uniform model encapsulating real-time agent state updates.
    Guarantees structured payload transmission across the WebSocket mesh.
    """
    event_type: TelemetryEventType
    trace_id: str
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    node_name: Optional[str] = None
    tool_name: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[float] = None
    
    # UX decoupled display policy
    ux_level: TelemetryUXLevel = TelemetryUXLevel.DEVELOPER
    
    # Data retention enforcement
    durability: TelemetryDurabilityTier = TelemetryDurabilityTier.TRANSIENT

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-assign appropriate UX mapping if not explicitly overridden in creation payload
        if "ux_level" not in data:
            self.ux_level = UX_LEVEL_MAP.get(self.event_type, TelemetryUXLevel.DEVELOPER)
        if "durability" not in data:
            self.durability = DURABILITY_MAP.get(self.event_type, TelemetryDurabilityTier.TRANSIENT)


