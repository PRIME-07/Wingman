from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from datetime import datetime
from backend.app.services.google.calendar import calendar_service
from backend.app.core.logging import logger

router = APIRouter()

@router.get("/events", response_model=List[Dict[str, Any]])
async def fetch_calendar_event_range(
    start: str = Query(..., description="ISO 8601 bounding start time (e.g. 2024-05-01T00:00:00Z)"),
    end: str = Query(..., description="ISO 8601 bounding end time (e.g. 2024-06-01T00:00:00Z)")
):
    """
    Retrieves calendar items falling strictly within the specified temporal boundaries.
    """
    logger.info(f"[API-Calendar] Inbound API range query: {start} -> {end}")
    try:
        events = await calendar_service.list_range_events(start_iso=start, end_iso=end)
        return events
    except PermissionError as pe:
        logger.warning(f"[API-Calendar] Token lock preventing fetch: {pe}")
        raise HTTPException(
            status_code=401, 
            detail="Google account credentials are not properly authorized. Please link your account."
        )
    except Exception as e:
        logger.error(f"[API-Calendar] Events endpoint failed querying timeframe: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed reading calendar matrix: {str(e)}"
        )

@router.get("/upcoming", response_model=Dict[str, Any])
async def fetch_upcoming_events(max_results: int = Query(5, description="Number of events to retrieve")):
    """
    Fetches the next few upcoming calendar entries for the user.
    """
    try:
        events = await calendar_service.list_upcoming_events(max_results=max_results)
        
        # Distill into clean minimized dicts
        formatted_events = []
        for evt in events:
            formatted_events.append({
                "summary": evt.get("summary"),
                "start": evt.get("start", {}),
                "end": evt.get("end", {}),
                "location": evt.get("location"),
                "status": evt.get("status"),
                "html_link": evt.get("htmlLink")
            })
            
        return {
            "success": True,
            "events": formatted_events,
            "count": len(formatted_events)
        }
    except PermissionError as pe:
        raise HTTPException(status_code=401, detail=str(pe))
    except Exception as e:
        logger.error(f"[API-Calendar] Upcoming fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error fetching schedule.")

from pydantic import BaseModel
from typing import Optional

class CreateEventPayload(BaseModel):
    summary: str
    start_iso: str
    end_iso: str
    description: Optional[str] = None
    location: Optional[str] = None
    timezone: str = "UTC"

class UpdateEventPayload(BaseModel):
    summary: Optional[str] = None
    start_iso: Optional[str] = None
    end_iso: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    timezone: str = "UTC"

@router.post("/events/create", response_model=Dict[str, Any])
async def api_create_event(payload: CreateEventPayload):
    """
    Creates a new Google Calendar event.
    """
    try:
        result = await calendar_service.create_event(
            summary=payload.summary,
            start_iso=payload.start_iso,
            end_iso=payload.end_iso,
            description=payload.description,
            location=payload.location,
            timezone=payload.timezone
        )
        return {
            "success": True,
            "event_id": result["event_id"],
            "html_link": result["html_link"]
        }
    except PermissionError as pe:
        raise HTTPException(status_code=401, detail=str(pe))
    except Exception as e:
        logger.error(f"[API-Calendar] Create event failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")

@router.patch("/events/{event_id}", response_model=Dict[str, Any])
async def api_update_event(event_id: str, payload: UpdateEventPayload):
    """
    Updates/Modifies details of an existing Google Calendar event.
    """
    try:
        result = await calendar_service.update_event(
            event_id=event_id,
            summary=payload.summary,
            start_iso=payload.start_iso,
            end_iso=payload.end_iso,
            description=payload.description,
            location=payload.location,
            timezone=payload.timezone
        )
        return result
    except PermissionError as pe:
        raise HTTPException(status_code=401, detail=str(pe))
    except Exception as e:
        logger.error(f"[API-Calendar] Update event failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update event: {str(e)}")

@router.delete("/events/{event_id}", response_model=Dict[str, Any])
async def api_delete_event(event_id: str):
    """
    Deletes/Cancels an existing Google Calendar event.
    """
    try:
        result = await calendar_service.delete_event(event_id=event_id)
        return result
    except PermissionError as pe:
        raise HTTPException(status_code=401, detail=str(pe))
    except Exception as e:
        logger.error(f"[API-Calendar] Delete event failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete event: {str(e)}")
