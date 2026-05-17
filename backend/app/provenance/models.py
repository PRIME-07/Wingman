from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class MemoryProvenance(BaseModel):
    """
    Rigidly tracks the point-of-origin details for permanent memories 
    to enable full lineage auditing and graph rollbacks.
    """
    session_id: str = Field(description="Originating conversation thread identifier.")
    trace_id: str = Field(description="Active graph trace sequence id.")
    run_id: str = Field(description="Direct runtime step execution run marker.")
    agent_node: str = Field(default="reflection", description="The internal node that suggested this memory.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    verification_justification: Optional[str] = Field(None, description="Outcome of anti-hallucination gateway audit.")
