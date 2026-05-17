from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any, List, Optional

class SessionCreate(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Optional custom UUID. Generated if omitted.")
    session_name: str = Field(default="New Conversation", description="Human-friendly label for isolation grouping.")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SessionUpdate(BaseModel):
    session_name: str = Field(..., description="Renamed title for the session.")

class SessionResponse(BaseModel):
    session_id: str
    session_name: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = {}

class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]
