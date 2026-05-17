from fastapi import APIRouter
from typing import List, Dict, Any
from backend.app.tools.registry import tool_registry
from backend.app.core.logging import logger

router = APIRouter()

@router.get("", response_model=List[Dict[str, Any]])
async def list_registered_assistant_tools():
    """
    Exposes simple metadata mapping of all active Wingman core plugins and tools.
    Powers the integration configuration modules in the front-end GUI.
    """
    logger.info("[API-Tools] Servicing request for full tool capabilities registry.")
    
    results = []
    for t in tool_registry.list_tools():
        results.append({
            "name": t.name,
            "description": t.description
        })
        
    return results
