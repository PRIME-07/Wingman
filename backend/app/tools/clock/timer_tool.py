from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext
from backend.app.core.logging import logger
from backend.app.services.clock.timer_runtime import timer_runtime

# Tool 1: Set Countdown Timer

class TimerSetInput(BaseModel):
    seconds: float = Field(..., description="Timer duration in seconds (e.g., 300 for 5 minutes).")
    label: str = Field("General Timer", description="Informative tag identifying the alarm purpose.")

class TimerSetTool(BaseWingmanTool):
    """
    Schedules a local async countdown.
    Fires structured alert telemetry once duration expires.
    """
    name = "timer_set"
    description = "Starts an active background countdown timer with a given label."
    args_schema = TimerSetInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        secs = args["seconds"]
        label = args["label"]
        session_id = context.metadata.get("session_id")
        
        logger.info(f"[TimerTool] Triggering setting of {secs}s alarm '{label}'...")
        
        # Artificial delay to ensure response delivery
        import asyncio
        await asyncio.sleep(1.0)
        
        timer_id = timer_runtime.create_timer(
            seconds=secs,
            label=label,
            session_id=session_id
        )
        
        return {
            "success": True,
            "timer_id": timer_id,
            "label": label,
            "duration_seconds": secs,
            "message": f"{int(secs)} seconds counting down!"
        }


# Tool 2: Cancel Timer

class TimerCancelInput(BaseModel):
    timer_id: str = Field(..., description="UUID string mapping to target timer to abort.")

class TimerCancelTool(BaseWingmanTool):
    """Aborts an unexpired scheduled task."""
    name = "timer_cancel"
    description = "Stops and cancels a running countdown timer before it expires."
    args_schema = TimerCancelInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        tid = args["timer_id"]
        
        logger.info(f"[TimerTool] Attempting cancellation of timer ID={tid}")
        success = timer_runtime.cancel_timer(tid)
        
        if success:
            return {"success": True, "message": f"Timer successfully terminated."}
        else:
            return {"success": False, "message": "Failed to cancel. Timer may already have completed or is invalid."}


# Tool 3: List Active Timers

class TimerListTool(BaseWingmanTool):
    """Lists running timers scoped to user context."""
    name = "timer_list"
    description = "Lists all currently active background timers and remaining durations."
    
    # No inputs required
    args_schema = None

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        session_id = context.metadata.get("session_id")
        
        active_list = timer_runtime.list_active_timers(session_id)
        
        return {
            "success": True,
            "active_timers": active_list,
            "count": len(active_list)
        }
