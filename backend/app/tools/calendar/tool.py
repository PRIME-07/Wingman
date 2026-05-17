from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext, wingman_interrupt
from backend.app.core.logging import logger
from backend.app.services.google.calendar import calendar_service

# Tool 1: Calendar Scheduling (Requires HITL)

class CalendarScheduleInput(BaseModel):
    summary: str = Field(..., description="Title of the meeting or event.")
    start_iso: str = Field(..., description="ISO 8601 start datetime string (e.g., '2026-05-15T09:00:00Z').")
    end_iso: str = Field(..., description="ISO 8601 end datetime string (e.g., '2026-05-15T10:00:00Z').")
    description: Optional[str] = Field(None, description="Detailed event notes.")
    location: Optional[str] = Field(None, description="Physical or virtual location link.")
    attendees: Optional[List[str]] = Field(None, description="List of email addresses to invite.")
    timezone: str = Field("UTC", description="Timezone of the input times.")

class CalendarScheduleTool(BaseWingmanTool):
    """
    Schedules a Google Calendar event. 
    Applies automatic Free-Busy scanning to detect collisions, 
    warns the user, and suspends logic until explicitly approved via HITL Interrupt.
    """
    name = "calendar_schedule"
    description = "Books a new event on the user's calendar. REQUIRES human approval."
    args_schema = CalendarScheduleInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        summary = args["summary"]
        start_iso = args["start_iso"]
        end_iso = args["end_iso"]
        
        try:
            # Perform preliminary automated collision checks as decision helper
            try:
                start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                
                busy_windows = await calendar_service.check_free_busy(start_dt, end_dt)
                collision_detected = len(busy_windows) > 0
            except Exception as ex:
                logger.warning(f"[CalendarTool] Premature parsing error during validation: {ex}")
                collision_detected = False
                busy_windows = []

            logger.info(f"[CalendarTool] Injecting HITL approval gate for '{summary}'. CollisionDetected={collision_detected}")
            
            # Step 1: Trigger user interaction pause
            decision = wingman_interrupt({
                "tool": "calendar_schedule",
                "prompt": f"Schedule '{summary}' on {start_iso}?",
                "data": {
                    "summary": summary,
                    "start_iso": start_iso,
                    "end_iso": end_iso,
                    "description": args.get("description"),
                    "attendees": args.get("attendees"),
                    "collision_detected": collision_detected,
                    "conflicting_events": busy_windows
                }
            }, context)
            
            # Step 2: Handle Response
            if decision.get("approved", False) is True:
                logger.info(f"[CalendarTool] Scheduling APPROVED. Writing event...")
                
                result = await calendar_service.create_event(
                    summary=summary,
                    start_iso=start_iso,
                    end_iso=end_iso,
                    description=args.get("description"),
                    location=args.get("location"),
                    attendees=args.get("attendees"),
                    timezone=args.get("timezone")
                )
                
                return {
                    "status": "Event Scheduled",
                    "event_id": result["event_id"],
                    "html_link": result["html_link"]
                }
            else:
                reason = decision.get("reason", "Cancelled by operator.")
                logger.warning(f"[CalendarTool] Event write REJECTED: {reason}")
                return {
                    "status": "Cancelled",
                    "reason": reason,
                    "instruction": "The scheduling was rejected. Offer to check alternative slots or find conflicting times."
                }
        
        except PermissionError as pe:
            logger.error(f"[CalendarTool] Auth missing: {pe}")
            return {"status": "Auth Failure", "error": str(pe)}
        except Exception as e:
            logger.error(f"[CalendarTool] Failed creation: {e}", exc_info=True)
            raise


# Tool 2: Calendar Auditing (Safe, No HITL needed)

class CalendarQueryInput(BaseModel):
    time_min: Optional[str] = Field(None, description="Optional ISO 8601 filter bound. Defaults to current timestamp.")
    time_max: Optional[str] = Field(None, description="Optional upper limit boundary filter.")
    max_results: int = Field(10, description="Limit of events returned.")

class CalendarQueryTool(BaseWingmanTool):
    """
    Audits user schedules. Performs non-destructive list lookups.
    Returns list of upcoming event items for conversational grounding.
    """
    name = "calendar_query"
    description = "Fetches current upcoming calendar entries to verify the user's schedule and availability."
    args_schema = CalendarQueryInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        try:
            events = await calendar_service.list_upcoming_events(max_results=args["max_results"])
            
            # Distill into clean minimized dicts to preserve context tokens
            formatted_events = []
            for evt in events:
                formatted_events.append({
                    "event_id": evt.get("id"),
                    "summary": evt.get("summary"),
                    "start": evt.get("start", {}).get("dateTime") or evt.get("start", {}).get("date"),
                    "end": evt.get("end", {}).get("dateTime") or evt.get("end", {}).get("date"),
                    "status": evt.get("status"),
                    "html_link": evt.get("htmlLink")
                })
                
            logger.info(f"[CalendarTool] Successfully fetched {len(formatted_events)} schedule events.")
            return {
                "success": True,
                "events": formatted_events,
                "summary": f"Found {len(formatted_events)} upcoming items."
            }
        except PermissionError as pe:
            return {"success": False, "error": str(pe), "instruction": "Unauthenticated. Request operator login."}
        except Exception as e:
            logger.error(f"[CalendarTool] Query failed: {e}")
            raise


# Tool 3: Calendar Modification (Requires HITL)

class CalendarModifyInput(BaseModel):
    event_id: str = Field(..., description="The unique Google Calendar Event ID to modify.")
    summary: Optional[str] = Field(None, description="Optional updated title of the meeting or event.")
    start_iso: Optional[str] = Field(None, description="Optional updated ISO 8601 start datetime string (e.g., '2026-05-15T09:00:00Z').")
    end_iso: Optional[str] = Field(None, description="Optional updated ISO 8601 end datetime string (e.g., '2026-05-15T10:00:00Z').")
    description: Optional[str] = Field(None, description="Optional updated detailed event notes.")
    location: Optional[str] = Field(None, description="Optional updated physical or virtual location link.")
    timezone: str = Field("UTC", description="Timezone of the updated input times.")

class CalendarModifyTool(BaseWingmanTool):
    """
    Modifies an existing Google Calendar event.
    Applies automatic Free-Busy scanning on changed times to detect collisions,
    warns the user, and suspends logic until approved via HITL Interrupt.
    """
    name = "calendar_modify"
    description = "Modifies an existing event's details or time on the user's calendar. REQUIRES human approval."
    args_schema = CalendarModifyInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        event_id = args["event_id"]
        start_iso = args.get("start_iso")
        end_iso = args.get("end_iso")
        summary = args.get("summary") or "Calendar Event Update"
        
        try:
            collision_detected = False
            busy_windows = []
            
            # Check collisions if timing updates are supplied
            if start_iso and end_iso:
                try:
                    start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                    
                    busy_windows = await calendar_service.check_free_busy(start_dt, end_dt)
                    collision_detected = len(busy_windows) > 0
                except Exception as ex:
                    logger.warning(f"[CalendarTool] Collision check error during modification: {ex}")

            logger.info(f"[CalendarTool] Injecting HITL approval gate for modifying event ID: {event_id}. Collision={collision_detected}")
            
            # Pause for Operator Clearance
            decision = wingman_interrupt({
                "tool": "calendar_modify",
                "prompt": f"Modify event details for '{summary}'?",
                "data": {
                    "event_id": event_id,
                    "summary": summary,
                    "start_iso": start_iso,
                    "end_iso": end_iso,
                    "description": args.get("description"),
                    "location": args.get("location"),
                    "collision_detected": collision_detected,
                    "conflicting_events": busy_windows
                }
            }, context)
            
            if decision.get("approved", False) is True:
                logger.info(f"[CalendarTool] Modification APPROVED. Committing updates...")
                
                result = await calendar_service.update_event(
                    event_id=event_id,
                    summary=args.get("summary"),
                    start_iso=start_iso,
                    end_iso=end_iso,
                    description=args.get("description"),
                    location=args.get("location"),
                    timezone=args.get("timezone")
                )
                
                return {
                    "status": "Event Modified",
                    "event_id": result["event_id"],
                    "html_link": result["html_link"]
                }
            else:
                reason = decision.get("reason", "Cancelled by operator.")
                logger.warning(f"[CalendarTool] Event modification REJECTED: {reason}")
                return {
                    "status": "Cancelled",
                    "reason": reason,
                    "instruction": "The modifications were rejected. Explain to the user and ask for adjusted guidelines."
                }
        except PermissionError as pe:
            return {"status": "Auth Failure", "error": str(pe)}
        except Exception as e:
            logger.error(f"[CalendarTool] Failed modification: {e}", exc_info=True)
            raise


# Tool 4: Calendar Deletion (Requires HITL)

class CalendarDeleteInput(BaseModel):
    event_id: str = Field(..., description="The unique Google Calendar Event ID to delete/cancel.")
    summary: Optional[str] = Field("Unspecified Event", description="The title or description of the event for Operator verification.")

class CalendarDeleteTool(BaseWingmanTool):
    """
    Deletes/cancels an existing Google Calendar event.
    REQUIRES operator HITL clearance before executing the deletion API.
    """
    name = "calendar_delete"
    description = "Deletes or cancels an existing event on the user's calendar. REQUIRES human approval."
    args_schema = CalendarDeleteInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        event_id = args["event_id"]
        summary = args.get("summary", "Calendar Event")
        
        try:
            logger.info(f"[CalendarTool] Injecting HITL approval gate for deleting event: '{summary}' (ID={event_id})")
            
            # Pause for Operator Clearance
            decision = wingman_interrupt({
                "tool": "calendar_delete",
                "prompt": f"Permanently delete/cancel event '{summary}' from calendar?",
                "data": {
                    "event_id": event_id,
                    "summary": summary
                }
            }, context)
            
            if decision.get("approved", False) is True:
                logger.info(f"[CalendarTool] Deletion APPROVED. Committing cancel...")
                
                result = await calendar_service.delete_event(event_id=event_id)
                
                return {
                    "status": "Event Deleted",
                    "event_id": result["event_id"]
                }
            else:
                reason = decision.get("reason", "Cancelled by operator.")
                logger.warning(f"[CalendarTool] Event deletion REJECTED: {reason}")
                return {
                    "status": "Cancelled",
                    "reason": reason,
                    "instruction": "The event cancellation was rejected. Confirm with the user that the event remains scheduled."
                }
        except PermissionError as pe:
            return {"status": "Auth Failure", "error": str(pe)}
        except Exception as e:
            logger.error(f"[CalendarTool] Failed deletion: {e}", exc_info=True)
            raise
