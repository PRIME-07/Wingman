from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any
import asyncio
from backend.app.services.google.docs import google_docs_service
from backend.app.services.google.sheets import google_sheets_service
from backend.app.services.google.calendar import calendar_service
from backend.app.memory.mongodb_client import mongo_client
from backend.app.core.logging import logger

router = APIRouter()

@router.get("", response_model=Dict[str, Any])
async def aggregate_multi_domain_search(q: str = Query(..., min_length=1)):
    """
    Aggregated Search Pipeline: Fanout keyword lookup across MongoDB system vault files,
    Google Drive text docs, and Google Calendar entries in parallel.
    """
    logger.info(f"[API-Search] Encountered global search lookup request for: '{q}'")
    
    try:
        # 1. Trigger non-blocking asynchronous tasks in parallel
        uploaded_task = mongo_client.search_documents(q)
        gdocs_task = google_docs_service.search_documents(q)
        gsheets_task = google_sheets_service.search_spreadsheets(q)
        calendar_task = calendar_service.search_events(q)
        
        # 2. Perform aggregated gathering to speed up responses
        uploaded_docs, google_docs, google_sheets, calendar_events = await asyncio.gather(
            uploaded_task,
            gdocs_task,
            gsheets_task,
            calendar_task,
            return_exceptions=True
        )
        
        # 3. Reconcile any failure states or permission blocks cleanly
        final_uploaded = []
        if not isinstance(uploaded_docs, Exception):
            for doc in uploaded_docs:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                if "uploaded_at" in doc:
                    doc["uploaded_at"] = doc["uploaded_at"].isoformat()
                final_uploaded.append(doc)
        else:
            logger.error(f"[API-Search] System Vault fetch failed during search: {uploaded_docs}")
            
        final_gdocs = []
        if not isinstance(google_docs, Exception):
            final_gdocs = google_docs
        else:
            logger.error(f"[API-Search] Google Docs retrieval failed: {google_docs}")

        final_gsheets = []
        if not isinstance(google_sheets, Exception):
            final_gsheets = google_sheets
        else:
            logger.error(f"[API-Search] Google Sheets search failed: {google_sheets}")

        final_calendar = []
        if not isinstance(calendar_events, Exception):
            final_calendar = calendar_events
        else:
            logger.error(f"[API-Search] Google Calendar search failed: {calendar_events}")

        return {
            "query": q,
            "uploadedDocs": final_uploaded,
            "googleDocs": final_gdocs,
            "googleSheets": final_gsheets,
            "calendarEvents": final_calendar
        }
        
    except Exception as e:
        logger.error(f"[API-Search] Unified Search pipeline collapsed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Integrated search query failed to respond: {str(e)}"
        )
