from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any, Optional
from backend.app.services.clock.timer_runtime import timer_runtime
from backend.app.core.logging import logger

router = APIRouter()

@router.get("/timers", response_model=Dict[str, Any])
async def list_active_timers(session_id: Optional[str] = None):
    """
    Lists all active background countdowns for the current session.
    Used by the Live Activities sidebar to show real-time progress.
    """
    logger.debug(f"[API-Clock] Fetching active timers for session: {session_id}")
    active = timer_runtime.list_active_timers(session_id)
    return {
        "success": True,
        "active_timers": active,
        "count": len(active)
    }

@router.post("/timers/cancel")
async def cancel_active_timer(payload: Dict[str, str] = Body(...)):
    """
    Aborts a running timer given its unique ID.
    """
    timer_id = payload.get("timer_id")
    if not timer_id:
        raise HTTPException(status_code=400, detail="Missing timer_id in request body")
        
    logger.info(f"[API-Clock] Request to cancel timer: {timer_id}")
    success = timer_runtime.cancel_timer(timer_id)
    
    if not success:
        return {"success": False, "message": "Timer not found or already completed."}
        
    return {"success": True, "message": "Timer cancelled successfully."}
