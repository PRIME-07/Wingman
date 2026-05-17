from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from datetime import datetime
from backend.app.scheduler.consolidation import run_micro_consolidation
from backend.app.core.logging import logger

router = APIRouter()

class MaintenanceTriggerRequest(BaseModel):
    pass

class MaintenanceTriggerResponse(BaseModel):
    success: bool
    message: str

@router.post("/consolidate", response_model=MaintenanceTriggerResponse)
async def trigger_manual_consolidation():
    """
    Maintenance Endpoint: Forces the micro-consolidation routine.
    Attempts async Redis enqueue first, falling back gracefully to synchronous
    execution if Redis infrastructure is not available.
    """
    logger.info(f"[API-Memory] Force trigger initiated.")
            
    # Strategy A: Decoupled High-Performance Redis Enqueue
    from backend.app.worker.scheduler import enqueue_background_task
    enqueued = await enqueue_background_task(
        "task_run_consolidation"
    )
    
    if enqueued:
        return MaintenanceTriggerResponse(
            success=True,
            message="Successfully enqueued consolidation task into Redis. Executing in background worker loop."
        )
        
    # Strategy B: Fallback Synchronous Run (Dev environments / Offline queues)
    logger.warning("[API-Memory] Redis queue unavailable. Falling back to Synchronous Foreground Execution...")
    success = await run_micro_consolidation()
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Consolidation pipeline failed. Consult backend runtime trace logs. Temporary data conserved."
        )
        
    return MaintenanceTriggerResponse(
        success=True,
        message="Consolidation pipeline completed flawlessly in local fallback mode. Graph updated & Temp store safely pruned."
    )
