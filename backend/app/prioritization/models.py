from enum import Enum
from pydantic import BaseModel, Field

class TaskPriorityTier(str, Enum):
    """Standardized execution tier mapping to system scheduling heuristics."""
    CRITICAL = "CRITICAL"     # Immediate synchronous path, bypass background queues
    HIGH = "HIGH"             # Accelerated interactive priority
    MEDIUM = "MEDIUM"         # Normal standard interactive user session
    LOW = "LOW"               # Latency tolerant tasks
    BACKGROUND = "BACKGROUND" # Deferred, non-blocking offline async runs

class PrioritizationConfig(BaseModel):
    """Dynamic resource constraint configurations driven by execution priority."""
    priority_tier: TaskPriorityTier = TaskPriorityTier.MEDIUM
    max_concurrency: int = 3
    timeout_seconds: int = 300
    retry_attempts: int = 2

def get_priority_config(tier: TaskPriorityTier) -> PrioritizationConfig:
    """Maps nominal priorities to tangible scheduling metrics."""
    if tier == TaskPriorityTier.CRITICAL:
        return PrioritizationConfig(priority_tier=tier, max_concurrency=10, timeout_seconds=60, retry_attempts=3)
    if tier == TaskPriorityTier.HIGH:
        return PrioritizationConfig(priority_tier=tier, max_concurrency=5, timeout_seconds=120, retry_attempts=2)
    if tier == TaskPriorityTier.BACKGROUND:
        return PrioritizationConfig(priority_tier=tier, max_concurrency=1, timeout_seconds=1800, retry_attempts=5)
    return PrioritizationConfig(priority_tier=tier)
