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


# Tool 5: Calendar Batch Scheduling (Requires HITL)

class BatchEventItem(BaseModel):
    summary: str = Field(..., description="Title of the meeting or event.")
    start_iso: Optional[str] = Field(None, description="ISO 8601 start datetime string (e.g., '2026-05-15T09:00:00Z') for timed events.")
    end_iso: Optional[str] = Field(None, description="ISO 8601 end datetime string (e.g., '2026-05-15T10:00:00Z') for timed events.")
    start_date: Optional[str] = Field(None, description="YYYY-MM-DD start date for all-day events.")
    end_date: Optional[str] = Field(None, description="YYYY-MM-DD end date for all-day events.")
    description: Optional[str] = Field(None, description="Detailed event notes.")
    location: Optional[str] = Field(None, description="Physical or virtual location link.")
    attendees: Optional[List[str]] = Field(None, description="List of email addresses to invite.")
    timezone: str = Field("UTC", description="Timezone of the input times.")
    recurrence: Optional[List[str]] = Field(None, description="Optional list of RRULE strings for recurring events.")

class CalendarBatchScheduleInput(BaseModel):
    events: List[BatchEventItem] = Field(..., description="List of events to schedule in batch.")

class CalendarBatchScheduleTool(BaseWingmanTool):
    """
    Schedules multiple Google Calendar events in a single operation.
    Runs automated Free-Busy scans for all timed events in the batch to detect collisions,
    and prompts for a single collective user confirmation via HITL Gateway.
    """
    name = "calendar_batch_schedule"
    description = "Books a batch of events on the user's calendar at once. REQUIRES human approval."
    args_schema = CalendarBatchScheduleInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        events = args["events"]
        
        try:
            batch_data = []
            for ev in events:
                collision_detected = False
                busy_windows = []
                
                # Check for collisions for timed events
                start_iso = ev.get("start_iso")
                end_iso = ev.get("end_iso")
                start_date = ev.get("start_date")
                end_date = ev.get("end_date")
                
                if start_iso and end_iso:
                    try:
                        start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                        
                        busy_windows = await calendar_service.check_free_busy(start_dt, end_dt)
                        collision_detected = len(busy_windows) > 0
                    except Exception as ex:
                        logger.warning(f"[CalendarBatchTool] Collision check error for '{ev.get('summary')}': {ex}")
                
                batch_data.append({
                    "summary": ev.get("summary"),
                    "start_iso": start_iso,
                    "end_iso": end_iso,
                    "start_date": start_date,
                    "end_date": end_date,
                    "description": ev.get("description"),
                    "location": ev.get("location"),
                    "attendees": ev.get("attendees"),
                    "timezone": ev.get("timezone", "UTC"),
                    "recurrence": ev.get("recurrence"),
                    "collision_detected": collision_detected,
                    "conflicting_events": busy_windows
                })

            logger.info(f"[CalendarBatchTool] Triggering batch HITL gate for {len(events)} events.")
            
            # Request single unified user approval
            decision = wingman_interrupt({
                "tool": "calendar_batch_schedule",
                "prompt": f"Schedule a batch of {len(events)} events on your calendar?",
                "data": {
                    "events": batch_data
                }
            }, context)
            
            if decision.get("approved", False) is True:
                logger.info(f"[CalendarBatchTool] Batch APPROVED. Writing events to Google Calendar...")
                
                # Extract any user modifications from decision extra info
                final_events = decision.get("extra", {}).get("events", batch_data)
                
                results = []
                for ev_info in final_events:
                    try:
                        res = await calendar_service.create_event(
                            summary=ev_info["summary"],
                            start_iso=ev_info.get("start_iso"),
                            end_iso=ev_info.get("end_iso"),
                            start_date=ev_info.get("start_date"),
                            end_date=ev_info.get("end_date"),
                            description=ev_info.get("description"),
                            location=ev_info.get("location"),
                            attendees=ev_info.get("attendees"),
                            timezone=ev_info.get("timezone", "UTC"),
                            recurrence=ev_info.get("recurrence")
                        )
                        results.append({
                            "summary": ev_info["summary"],
                            "status": "Created",
                            "event_id": res.get("event_id"),
                            "html_link": res.get("html_link")
                        })
                    except Exception as ex:
                        logger.error(f"[CalendarBatchTool] Failed creating batch item '{ev_info['summary']}': {ex}")
                        results.append({
                            "summary": ev_info["summary"],
                            "status": "Failed",
                            "error": str(ex)
                        })
                
                return {
                    "status": "Batch Processed",
                    "results": results
                }
            else:
                reason = decision.get("reason", "Cancelled by operator.")
                logger.warning(f"[CalendarBatchTool] Batch event write REJECTED: {reason}")
                return {
                    "status": "Cancelled",
                    "reason": reason,
                    "instruction": "The batch scheduling was rejected by the operator."
                }
                
        except PermissionError as pe:
            logger.error(f"[CalendarBatchTool] Auth missing: {pe}")
            return {"status": "Auth Failure", "error": str(pe)}
        except Exception as e:
            logger.error(f"[CalendarBatchTool] Failed batch creation: {e}", exc_info=True)
            raise


# Tool 6: Calendar Batch Modification (Requires HITL)

class BatchModifyEventItem(BaseModel):
    event_id: str = Field(..., description="The unique Google Calendar Event ID to modify.")
    summary: Optional[str] = Field(None, description="Optional updated title of the meeting or event.")
    start_iso: Optional[str] = Field(None, description="Optional updated ISO 8601 start datetime string (e.g., '2026-05-15T09:00:00Z').")
    end_iso: Optional[str] = Field(None, description="Optional updated ISO 8601 end datetime string (e.g., '2026-05-15T10:00:00Z').")
    description: Optional[str] = Field(None, description="Optional updated detailed event notes.")
    location: Optional[str] = Field(None, description="Optional updated physical or virtual location link.")
    timezone: str = Field("UTC", description="Timezone of the updated input times.")

class CalendarBatchModifyInput(BaseModel):
    events: List[BatchModifyEventItem] = Field(..., description="List of event modifications to process.")

class CalendarBatchModifyTool(BaseWingmanTool):
    """
    Modifies multiple existing Google Calendar events in a single operation.
    Applies automatic Free-Busy scanning on changed times to detect collisions,
    and prompts for a single collective user confirmation via HITL Gateway.
    """
    name = "calendar_batch_modify"
    description = "Modifies a batch of existing events on the user's calendar at once. REQUIRES human approval."
    args_schema = CalendarBatchModifyInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        events = args["events"]
        
        try:
            batch_data = []
            for ev in events:
                collision_detected = False
                busy_windows = []
                
                # Check for collisions for modified timed events if start/end are provided
                start_iso = ev.get("start_iso")
                end_iso = ev.get("end_iso")
                
                if start_iso and end_iso:
                    try:
                        start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                        
                        busy_windows = await calendar_service.check_free_busy(start_dt, end_dt)
                        collision_detected = len(busy_windows) > 0
                    except Exception as ex:
                        logger.warning(f"[CalendarBatchModifyTool] Collision check error for '{ev.get('summary')}': {ex}")
                
                batch_data.append({
                    "event_id": ev["event_id"],
                    "summary": ev.get("summary") or "Calendar Event Update",
                    "start_iso": start_iso,
                    "end_iso": end_iso,
                    "description": ev.get("description"),
                    "location": ev.get("location"),
                    "timezone": ev.get("timezone", "UTC"),
                    "collision_detected": collision_detected,
                    "conflicting_events": busy_windows
                })

            logger.info(f"[CalendarBatchModifyTool] Triggering batch modify HITL gate for {len(events)} events.")
            
            # Request single unified user approval
            decision = wingman_interrupt({
                "tool": "calendar_batch_modify",
                "prompt": f"Modify a batch of {len(events)} events on your calendar?",
                "data": {
                    "events": batch_data
                }
            }, context)
            
            if decision.get("approved", False) is True:
                logger.info(f"[CalendarBatchModifyTool] Batch Modify APPROVED. Modifying events in Google Calendar...")
                
                # Extract any user modifications from decision extra info
                final_events = decision.get("extra", {}).get("events", batch_data)
                
                results = []
                for ev_info in final_events:
                    try:
                        res = await calendar_service.update_event(
                            event_id=ev_info["event_id"],
                            summary=ev_info.get("summary"),
                            start_iso=ev_info.get("start_iso"),
                            end_iso=ev_info.get("end_iso"),
                            description=ev_info.get("description"),
                            location=ev_info.get("location"),
                            timezone=ev_info.get("timezone", "UTC")
                        )
                        results.append({
                            "event_id": ev_info["event_id"],
                            "summary": ev_info.get("summary"),
                            "status": "Modified",
                            "html_link": res.get("html_link")
                        })
                    except Exception as ex:
                        logger.error(f"[CalendarBatchModifyTool] Failed modifying batch item '{ev_info.get('summary')}': {ex}")
                        results.append({
                            "event_id": ev_info["event_id"],
                            "summary": ev_info.get("summary"),
                            "status": "Failed",
                            "error": str(ex)
                        })
                
                return {
                    "status": "Batch Modified Processed",
                    "results": results
                }
            else:
                reason = decision.get("reason", "Cancelled by operator.")
                logger.warning(f"[CalendarBatchModifyTool] Batch event modify REJECTED: {reason}")
                return {
                    "status": "Cancelled",
                    "reason": reason,
                    "instruction": "The batch modification was rejected by the operator."
                }
                
        except PermissionError as pe:
            logger.error(f"[CalendarBatchModifyTool] Auth missing: {pe}")
            return {"status": "Auth Failure", "error": str(pe)}
        except Exception as e:
            logger.error(f"[CalendarBatchModifyTool] Failed batch modify: {e}", exc_info=True)
            raise


# Tool 7: Calendar Batch Deletion (Requires HITL)

class BatchDeleteEventItem(BaseModel):
    event_id: str = Field(..., description="The unique Google Calendar Event ID to delete/cancel.")
    summary: Optional[str] = Field("Unspecified Event", description="The title or description of the event for Operator verification.")
    start_iso: Optional[str] = Field(None, description="Optional start ISO datetime for verification.")
    end_iso: Optional[str] = Field(None, description="Optional end ISO datetime for verification.")
    start_date: Optional[str] = Field(None, description="Optional start date for all-day verification.")
    end_date: Optional[str] = Field(None, description="Optional end date for all-day verification.")
    description: Optional[str] = Field(None, description="Optional description.")
    location: Optional[str] = Field(None, description="Optional location.")

class CalendarBatchDeleteInput(BaseModel):
    events: List[BatchDeleteEventItem] = Field(..., description="List of events to delete/cancel in batch.")

class CalendarBatchDeleteTool(BaseWingmanTool):
    """
    Deletes/cancels multiple Google Calendar events in a single operation.
    Prompts for a single collective user confirmation via HITL Gateway.
    """
    name = "calendar_batch_delete"
    description = "Deletes or cancels a batch of existing events on the user's calendar at once. REQUIRES human approval."
    args_schema = CalendarBatchDeleteInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        events = args["events"]
        
        try:
            batch_data = []
            for ev in events:
                batch_data.append({
                    "event_id": ev["event_id"],
                    "summary": ev.get("summary") or "Calendar Event",
                    "start_iso": ev.get("start_iso"),
                    "end_iso": ev.get("end_iso"),
                    "start_date": ev.get("start_date"),
                    "end_date": ev.get("end_date"),
                    "description": ev.get("description"),
                    "location": ev.get("location")
                })

            logger.info(f"[CalendarBatchDeleteTool] Triggering batch delete HITL gate for {len(events)} events.")
            
            # Request single unified user approval
            decision = wingman_interrupt({
                "tool": "calendar_batch_delete",
                "prompt": f"Cancel/delete a batch of {len(events)} events from your calendar?",
                "data": {
                    "events": batch_data
                }
            }, context)
            
            if decision.get("approved", False) is True:
                logger.info(f"[CalendarBatchDeleteTool] Batch Delete APPROVED. Deleting events from Google Calendar...")
                
                # Extract events list (in case any specific deletions are filtered or modified)
                final_events = decision.get("extra", {}).get("events", batch_data)
                
                results = []
                for ev_info in final_events:
                    try:
                        res = await calendar_service.delete_event(event_id=ev_info["event_id"])
                        results.append({
                            "event_id": ev_info["event_id"],
                            "summary": ev_info.get("summary"),
                            "status": "Deleted"
                        })
                    except Exception as ex:
                        logger.error(f"[CalendarBatchDeleteTool] Failed deleting batch item '{ev_info.get('summary')}': {ex}")
                        results.append({
                            "event_id": ev_info["event_id"],
                            "summary": ev_info.get("summary"),
                            "status": "Failed",
                            "error": str(ex)
                        })
                
                return {
                    "status": "Batch Deletion Processed",
                    "results": results
                }
            else:
                reason = decision.get("reason", "Cancelled by operator.")
                logger.warning(f"[CalendarBatchDeleteTool] Batch event delete REJECTED: {reason}")
                return {
                    "status": "Cancelled",
                    "reason": reason,
                    "instruction": "The batch deletion was rejected by the operator."
                }
                
        except PermissionError as pe:
            logger.error(f"[CalendarBatchDeleteTool] Auth missing: {pe}")
            return {"status": "Auth Failure", "error": str(pe)}
        except Exception as e:
            logger.error(f"[CalendarBatchDeleteTool] Failed batch delete: {e}", exc_info=True)
            raise


