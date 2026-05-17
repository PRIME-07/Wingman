from pydantic import BaseModel, Field

class ToolCapability(BaseModel):
    """State metrics reflecting real-world tool usability in real-time."""
    available: bool = True
    authenticated: bool = True
    quota_ok: bool = True
    provider_reachable: bool = True
    reason: str = "Operational"
