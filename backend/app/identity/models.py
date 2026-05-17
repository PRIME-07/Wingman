from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime

class LinkedIdentity(BaseModel):
    """Models an active connection mapping to an external provider account."""
    provider: str  # e.g. "google", "slack"
    email: Optional[str] = None
    user_id: Optional[str] = None  # External system user identifier
    scopes: List[str] = Field(default_factory=list)
    connected_at: datetime = Field(default_factory=datetime.utcnow)
    active: bool = True

class UserIdentityMap(BaseModel):
    """
    Centralized container resolving a local Wingman user UUID to
    an extensible dictionary of real third-party connections.
    """
    identity_id: str
    display_name: str = "Wingman User"
    identities: Dict[str, LinkedIdentity] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
