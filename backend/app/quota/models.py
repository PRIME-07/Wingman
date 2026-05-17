from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict

class ProviderQuota(BaseModel):
    """Maintains real-time usage numbers against static administrative allocations."""
    provider: str
    daily_limit: int
    current_count: int = 0
    reset_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def ok(self) -> bool:
        return self.current_count < self.daily_limit
