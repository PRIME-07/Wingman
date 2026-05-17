from typing import Any, Dict
from backend.app.authenticity.models import AuthenticityLevel, ExecutionAuthenticity

def extract_authenticity(payload: Any) -> ExecutionAuthenticity:
    """
    Dynamically harvests authenticity metrics from varying service responses.
    Standardizes output schema checking for 'simulated' fields and structural fallbacks.
    """
    if not isinstance(payload, dict):
        # For simple responses, assume standard REAL execution unless empty
        return ExecutionAuthenticity(
            authenticity=AuthenticityLevel.REAL if payload is not None else AuthenticityLevel.FAILED,
            simulated=False,
            provider_connected=True
        )

    # Detect simulator layer fields
    is_sim = payload.get("simulated", False) or payload.get("is_mock", False)
    prov_conn = payload.get("provider_connected", True)
    
    if is_sim:
        prov_conn = payload.get("provider_connected", False)  # Usually false if simulated unless explicitly True
        return ExecutionAuthenticity(
            authenticity=AuthenticityLevel.SIMULATED,
            simulated=True,
            provider_connected=prov_conn,
            confidence_penalty=0.5  # Lower confidence by 50%
        )
        
    if payload.get("degraded", False):
        return ExecutionAuthenticity(
            authenticity=AuthenticityLevel.DEGRADED,
            simulated=False,
            provider_connected=True,
            confidence_penalty=0.2
        )
        
    if payload.get("partial", False):
         return ExecutionAuthenticity(
            authenticity=AuthenticityLevel.PARTIAL,
            simulated=True,
            provider_connected=True,
            confidence_penalty=0.3
        )

    # Default to successful real execution
    return ExecutionAuthenticity(
        authenticity=AuthenticityLevel.REAL,
        simulated=False,
        provider_connected=True
    )
