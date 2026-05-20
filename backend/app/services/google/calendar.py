from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from backend.app.core.logging import logger
from backend.app.services.google.oauth import google_oauth_manager

class CalendarService:
    """
    Wraps Google Calendar API v3 logic.
    Exposes methods for calendar state audits, atomic scheduling, and free-busy evaluations.
    """

    async def _get_client(self) -> Any:
        """Retrieves authorized discovery clients for the Calendar API."""
        creds = await google_oauth_manager.get_authenticated_credentials()
        if not creds:
            raise PermissionError("Google account credentials are not linked or valid.")
        return build("calendar", "v3", credentials=creds)

    async def check_free_busy(
        self, 
        start_time: datetime, 
        end_time: datetime, 
        calendar_id: str = "primary"
    ) -> List[Dict[str, str]]:
        """
        Performs low-latency Google Free-Busy query to detect active event collisions.
        Returns a list of conflicting 'busy' windows within the queried temporal boundaries.
        """
        try:
            client = await self._get_client()
            
            body = {
                "timeMin": start_time.isoformat() + "Z",
                "timeMax": end_time.isoformat() + "Z",
                "items": [{"id": calendar_id}]
            }
            
            logger.info(f"[CalendarService] Running FreeBusy check from {body['timeMin']} to {body['timeMax']}.")
            response = client.freebusy().query(body=body).execute()
            
            calendar_data = response.get("calendars", {}).get(calendar_id, {})
            busy_slots = calendar_data.get("busy", [])
            
            logger.debug(f"[CalendarService] Identified {len(busy_slots)} collision intervals.")
            return busy_slots
        except Exception as e:
            logger.error(f"[CalendarService] FreeBusy lookup failing: {e}", exc_info=True)
            raise

    async def create_event(
        self,
        summary: str,
        start_iso: Optional[str] = None,
        end_iso: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        timezone: str = "UTC",
        recurrence: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Commits a calendar event directly to Google servers.
        Supports customized attendee alerts and dynamic description binding.
        """
        try:
            client = await self._get_client()
            
            event_body = {
                "summary": summary,
                "description": description or "",
                "location": location or ""
            }
            
            if start_date and end_date:
                event_body["start"] = {
                    "date": start_date
                }
                event_body["end"] = {
                    "date": end_date
                }
            else:
                event_body["start"] = {
                    "dateTime": start_iso,
                    "timeZone": timezone
                }
                event_body["end"] = {
                    "dateTime": end_iso,
                    "timeZone": timezone
                }
                
            if recurrence:
                event_body["recurrence"] = recurrence
            
            if attendees:
                event_body["attendees"] = [{"email": email} for email in attendees]
                # Auto send notification emails on commit
                event_body["sendUpdates"] = "all"

            logger.info(f"[CalendarService] Attempting scheduled write for: '{summary}' [{start_iso}]")
            
            event = client.events().insert(
                calendarId="primary",
                body=event_body,
                sendUpdates="all" if attendees else "none"
            ).execute()
            
            logger.info(f"[CalendarService] Created Event ID={event.get('id')}.")
            return {
                "success": True,
                "event_id": event.get("id"),
                "html_link": event.get("htmlLink"),
                "status": event.get("status")
            }
        except Exception as e:
            logger.error(f"[CalendarService] Failed to insert calendar event: {e}")
            raise

    async def list_upcoming_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """Queries active queue of impending calendar bindings from current timestamp forward."""
        try:
            client = await self._get_client()
            
            now_str = datetime.utcnow().isoformat() + "Z"
            
            logger.info("[CalendarService] Querying list of upcoming calendar events...")
            events_result = client.events().list(
                calendarId="primary",
                timeMin=now_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            return events_result.get("items", [])
        except Exception as e:
            logger.error(f"[CalendarService] List events command aborted: {e}")
            return []

    async def search_events(self, query: str, max_results: int = 15) -> List[Dict[str, Any]]:
        """
        Combines full-text Google API queries with a robust local substring filter
        on recent/upcoming events to support partial prefix matches (e.g., "shra" for "Shravani").
        """
        try:
            import asyncio
            client = await self._get_client()
            logger.info(f"[CalendarService] Performing dual-layered search for keyword: '{query}'")
            
            def run_api_query():
                # Task A: Full-text query (handles exact whole words across historical limits)
                try:
                    return client.events().list(
                        calendarId="primary",
                        q=query,
                        maxResults=max_results * 2,
                        singleEvents=False
                    ).execute().get("items", [])
                except Exception as ex:
                    logger.warning(f"[CalendarService] Full-text index query failed: {ex}")
                    return []

            def run_broad_query():
                # Task B: Broad temporal window (captures upcoming/recent events for local prefix filtering)
                now = datetime.utcnow()
                time_min = (now - timedelta(days=365)).isoformat() + "Z"
                time_max = (now + timedelta(days=365 * 2)).isoformat() + "Z"
                try:
                    return client.events().list(
                        calendarId="primary",
                        timeMin=time_min,
                        timeMax=time_max,
                        maxResults=250,
                        singleEvents=False
                    ).execute().get("items", [])
                except Exception as ex:
                    logger.warning(f"[CalendarService] Broad local-pool query failed: {ex}")
                    return []

            loop = asyncio.get_event_loop()
            
            # Execute both network calls concurrently via thread executor (blocking client IO)
            api_hits, broad_pool = await asyncio.gather(
                loop.run_in_executor(None, run_api_query),
                loop.run_in_executor(None, run_broad_query)
            )
            
            # Apply Python-side case-insensitive substring filtering for premium prefix match support
            q_lower = query.lower()
            filtered_broad = []
            for ev in broad_pool:
                summary = ev.get("summary", "").lower()
                description = ev.get("description", "").lower()
                if q_lower in summary or q_lower in description:
                    filtered_broad.append(ev)
                    
            # Merge datasets and eliminate duplicates securely
            seen_ids = set()
            merged_items = []
            
            # Prioritize local prefix matches first
            for item in filtered_broad + api_hits:
                item_id = item.get("id")
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    merged_items.append(item)
                    
            # Enforce chronological ordering
            merged_items.sort(key=lambda ev: ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or "")
            
            return merged_items[:max_results]
        except (PermissionError, Exception) as e:
            logger.warning(f"[CalendarService] Dual-layered search overall failure: {e}. Returning empty list.")
            return []

    async def list_range_events(self, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Queries events residing purely within an exact start/end window."""
        try:
            client = await self._get_client()
            logger.info(f"[CalendarService] Fetching bounded events window: {start_iso} to {end_iso}")
            
            events_result = client.events().list(
                calendarId="primary",
                timeMin=start_iso,
                timeMax=end_iso,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            return events_result.get("items", [])
        except (PermissionError, Exception) as e:
            logger.warning(f"[CalendarService] Events window failure: {e}. Returning empty range.")
            return []

    async def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start_iso: Optional[str] = None,
        end_iso: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        timezone: str = "UTC",
        recurrence: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Updates an existing calendar event using Google's patch/update API.
        """
        try:
            client = await self._get_client()
            
            # Fetch existing event first to perform selective updates
            event = client.events().get(calendarId="primary", eventId=event_id).execute()
            
            if summary is not None:
                event["summary"] = summary
            if description is not None:
                event["description"] = description
            if location is not None:
                event["location"] = location
                
            if start_date is not None and end_date is not None:
                event["start"] = {
                    "date": start_date
                }
                event["end"] = {
                    "date": end_date
                }
            elif start_iso is not None and end_iso is not None:
                event["start"] = {
                    "dateTime": start_iso,
                    "timeZone": timezone
                }
                event["end"] = {
                    "dateTime": end_iso,
                    "timeZone": timezone
                }
                
            if recurrence is not None:
                if len(recurrence) == 0:
                    event["recurrence"] = None
                else:
                    event["recurrence"] = recurrence
                
            logger.info(f"[CalendarService] Attempting scheduled update for event ID: {event_id}")
            updated_event = client.events().update(
                calendarId="primary",
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info(f"[CalendarService] Successfully updated Event ID={updated_event.get('id')}.")
            return {
                "success": True,
                "event_id": updated_event.get("id"),
                "html_link": updated_event.get("htmlLink"),
                "status": updated_event.get("status")
            }
        except Exception as e:
            logger.error(f"[CalendarService] Failed to update calendar event {event_id}: {e}")
            raise

    async def delete_event(self, event_id: str) -> Dict[str, Any]:
        """
        Deletes/cancels an existing calendar event using Google's delete API.
        """
        try:
            client = await self._get_client()
            logger.info(f"[CalendarService] Attempting deletion of event ID: {event_id}")
            
            client.events().delete(
                calendarId="primary",
                eventId=event_id
            ).execute()
            
            logger.info(f"[CalendarService] Successfully deleted Event ID={event_id}.")
            return {
                "success": True,
                "event_id": event_id
            }
        except Exception as e:
            logger.error(f"[CalendarService] Failed to delete calendar event {event_id}: {e}")
            raise

# Singleton wrapper
calendar_service = CalendarService()
