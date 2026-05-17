from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel

class AuthenticityLevel(str, Enum):
    """Defines levels of operational reality during tool executions."""
    REAL = "REAL"           # True production API interaction occurred successfully
    SIMULATED = "SIMULATED" # Graceful developer override/mock fallback triggered
    PARTIAL = "PARTIAL"     # Some parts of execution were real, others simulated
    DEGRADED = "DEGRADED"   # Successful but suffered extreme latency or data omission
    FAILED = "FAILED"       # Absolute operational failure

class ExecutionAuthenticity(BaseModel):
    """Comprehensive audit signature proving runtime operation integrity."""
    authenticity: AuthenticityLevel = AuthenticityLevel.REAL
    simulated: bool = False
    provider_connected: bool = True
    confidence_penalty: float = 0.0  # Multiplier used by planners to degrade confidence
