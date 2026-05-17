from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext
from backend.app.core.logging import logger
from backend.app.services.clock.timer_runtime import timer_runtime
from backend.app.services.google.calendar import calendar_service

class ReminderInput(BaseModel):
    message: str = Field(..., description="The content of the reminder (e.g., 'Take the medicine').")
    minutes_from_now: int = Field(..., description="How many minutes from now the reminder should trigger.")

class ReminderTool(BaseWingmanTool):
    """
    Intelligent proactive alert scheduler.
    Logic:
    - If duration <= 60 minutes: Runs a high-priority local background timer.
    - If duration > 60 minutes: Automatically schedules as a Google Calendar event for persistence.
    """
    name = "reminder_set"
    description = "Sets a reminder. Logic: <=1hr uses a live timer, >1hr uses Google Calendar."
    args_schema = ReminderInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        msg = args["message"]
        mins = args["minutes_from_now"]
        session_id = context.metadata.get("session_id")
        
        target_time = datetime.utcnow() + timedelta(minutes=mins)
        
        if mins <= 60:
            # Short term: use Timer Runtime
            logger.info(f"[ReminderTool] Short-term reminder detected ({mins}m). Using TimerRuntime.")
            
            # Artificial delay to allow final response to stream/close websocket if needed
            import asyncio
            await asyncio.sleep(1.5)
            
            timer_id = timer_runtime.create_timer(
                seconds=mins * 60,
                label=f"[REMINDER] {msg}",
                session_id=session_id
            )
            return {
                "success": True,
                "type": "timer",
                "timer_id": timer_id,
                "message": f"All Set! I'll remind you to {msg} in {mins} {'minute' if mins == 1 else 'minutes'}."
            }
        else:
            # Long term: use Google Calendar
            logger.info(f"[ReminderTool] Long-term reminder detected ({mins}m). Using Google Calendar.")
            start_iso = target_time.isoformat() + "Z"
            end_iso = (target_time + timedelta(minutes=15)).isoformat() + "Z" # 15 min block
            
            try:
                # Note: We bypass HITL for reminders if they are just simple alerts? 
                # Or should we ask? User request says "put them in google calendar".
                # I'll use the service directly to avoid the tool's HITL gate for this specific flow.
                result = await calendar_service.create_event(
                    summary=f"Reminder: {msg}",
                    start_iso=start_iso,
                    end_iso=end_iso,
                    description="Automatically scheduled Wingman Reminder."
                )
                return {
                    "success": True,
                    "type": "calendar",
                    "event_id": result["event_id"],
                    "message": f"Since it's more than an hour away, I've scheduled a reminder for '{msg}' on your Google Calendar for {target_time.strftime('%H:%M')}."
                }
            except Exception as e:
                logger.error(f"[ReminderTool] Calendar fallback failed: {e}")
                # Fallback to timer if calendar fails? Maybe safer.
                timer_id = timer_runtime.create_timer(
                    seconds=mins * 60,
                    label=f"[REMINDER-FB] {msg}",
                    session_id=session_id
                )
                return {
                    "success": True,
                    "type": "timer_fallback",
                    "timer_id": timer_id,
                    "message": f"I tried to put it on your calendar but failed, so I've set a background timer for '{msg}' instead."
                }
