from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext, wingman_interrupt
from backend.app.core.logging import logger
from backend.app.services.google.sheets import google_sheets_service

# Memory Sync Helpers

def _serialize_sheet_to_text(values: List[List[Any]]) -> str:
    """Converts two-dimensional array into a clean tabular CSV-like markdown stream."""
    if not values:
        return ""
    lines = []
    for row in values:
        row_strs = [str(cell) if cell is not None else "" for cell in row]
        lines.append(" | ".join(row_strs))
    return "\n".join(lines)

async def _sync_spreadsheet_to_memory(sheet_id: str, title: Optional[str], context: ToolExecutionContext):
    """Reads full spreadsheet, processes to markdown, and updates both MongoDB and Pinecone semantic memory."""
    try:
        from backend.app.services.documents.manager import document_manager
        
        # Resolve sheet title if unavailable
        if not title:
            title = await google_sheets_service.get_spreadsheet_title(sheet_id)
            
        # Pull grid data range
        read_res = await google_sheets_service.read_spreadsheet(sheet_id, "Sheet1!A:Z")
        values = read_res.get("values", [])
        content = _serialize_sheet_to_text(values)
        
        await document_manager.ingest_virtual_asset(
            asset_id=sheet_id,
            title=title,
            content=content,
            asset_type="google_sheet",
            session_id=context.metadata.get("session_id"),
            url=f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        )
        logger.info(f"[SheetsTool] Atomic virtual synchronizer complete for sheet {sheet_id} ('{title}').")
    except Exception as e:
        logger.warning(f"[SheetsTool] Asynchronous semantic ingest experienced minor failure: {e}")

# Tool 1: Create Spreadsheet (Requires HITL)

class SheetsCreateInput(BaseModel):
    title: str = Field(..., description="Desired title for the new Google Spreadsheet.")

class SheetsCreateTool(BaseWingmanTool):
    """
    Instantiates a blank Google Sheet. Operates under HITL clearance
    to prevent agentic storage pollution.
    """
    name = "google_sheets_create"
    description = "Creates a new empty Google Spreadsheet in Drive. REQUIRES human clearance."
    args_schema = SheetsCreateInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        title = args["title"]
        
        logger.info(f"[SheetsTool] Prompting confirmation for spreadsheet creation: '{title}'")
        
        decision = wingman_interrupt({
            "tool": "google_sheets_create",
            "prompt": f"Create spreadsheet titled '{title}'?",
            "data": {"title": title}
        }, context)
        
        if decision.get("approved", False) is True:
            result = await google_sheets_service.create_spreadsheet(title)
            
            # Synchronize initial empty sheet structure
            try:
                from backend.app.services.documents.manager import document_manager
                await document_manager.ingest_virtual_asset(
                    asset_id=result["spreadsheet_id"],
                    title=title,
                    content="", # Starts fresh
                    asset_type="google_sheet",
                    session_id=context.metadata.get("session_id"),
                    url=result["url"]
                )
                logger.info(f"[SheetsTool] Cataloged initial empty spreadsheet {result['spreadsheet_id']} in memory engine.")
            except Exception as sync_err:
                logger.warning(f"[SheetsTool] Non-fatal initial registry sync failure: {sync_err}")

            return {
                "status": "Created Successfully",
                "spreadsheet_id": result["spreadsheet_id"],
                "url": result["url"]
            }
        else:
            return {"status": "Cancelled", "reason": decision.get("reason", "Operator aborted write.")}


# Tool 2: Read Spreadsheet (Safe)

class SheetsReadInput(BaseModel):
    spreadsheet_id: str = Field(..., description="Google Spreadsheet Unique ID.")
    range_name: str = Field("Sheet1!A:Z", description="The sheet and range to read (A1 notation), e.g., 'Sheet1!A1:E10'. Defaults to whole first sheet range.")

class SheetsReadTool(BaseWingmanTool):
    """
    Extracts cell values from a spreadsheet.
    Enables ingestion of tabular persistent data contexts into Wingman context.
    """
    name = "google_sheets_read"
    description = "Reads and extracts cell values from a specified range in a Google Spreadsheet."
    args_schema = SheetsReadInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        sheet_id = args["spreadsheet_id"]
        range_name = args["range_name"]
        logger.info(f"[SheetsTool] Triggering read operation for SheetID={sheet_id} at range='{range_name}'")
        
        try:
            result = await google_sheets_service.read_spreadsheet(sheet_id, range_name)
            
            # Proactive background semantic sync on read: keeps memories
            # aligned with manual edits in the web app!
            await _sync_spreadsheet_to_memory(sheet_id, title=None, context=context)
            
            return {
                "success": True,
                "spreadsheet_id": result["spreadsheet_id"],
                "range": result["range"],
                "values": result["values"],
                "summary": f"Successfully read {result['row_count']} rows of data."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# Tool 3: Append Spreadsheet Rows (Requires HITL)

class SheetsAppendInput(BaseModel):
    spreadsheet_id: str = Field(..., description="Google Spreadsheet ID to update.")
    values: List[List[Any]] = Field(..., description="A two-dimensional array of data values to append as new rows.")
    range_name: str = Field("Sheet1!A1", description="Target range to search for starting boundaries, e.g. 'Sheet1!A1'.")

class SheetsAppendTool(BaseWingmanTool):
    """
    Appends multiple rows of dynamic structured data. Requires HITL.
    """
    name = "google_sheets_append"
    description = "Appends new rows of data to a Google Spreadsheet. REQUIRES user review."
    args_schema = SheetsAppendInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        sheet_id = args["spreadsheet_id"]
        values = args["values"]
        range_name = args["range_name"]
        
        decision = wingman_interrupt({
            "tool": "google_sheets_append",
            "prompt": f"Append {len(values)} rows to spreadsheet?",
            "data": {
                "spreadsheet_id": sheet_id,
                "range_name": range_name,
                "values": values
            }
        }, context)
        
        if decision.get("approved", False) is True:
            # Allow manual payload override if supplied in user decision payload
            final_values = decision.get("values", values)
            
            res = await google_sheets_service.append_rows(sheet_id, final_values, range_name)
            
            # Background synchronization hook
            await _sync_spreadsheet_to_memory(sheet_id, title=None, context=context)
            
            return {
                "status": "Data Appended Successfully",
                "spreadsheet_id": sheet_id,
                "details": res.get("updates", {})
            }
        else:
            return {"status": "Append Cancelled", "reason": decision.get("reason", "Declined.")}


# Tool 4: Update Spreadsheet Range (Requires HITL)

class SheetsUpdateInput(BaseModel):
    spreadsheet_id: str = Field(..., description="Google Spreadsheet ID to modify.")
    range_name: str = Field(..., description="The specific A1 notation range to overwrite, e.g. 'Sheet1!B2:C4'.")
    values: List[List[Any]] = Field(..., description="A two-dimensional array of replacement values.")

class SheetsUpdateTool(BaseWingmanTool):
    """
    Overwrites a specific range of cells in a sheet. Extremely powerful, absolutely requires HITL.
    """
    name = "google_sheets_update"
    description = "Overwrites cell values in a specific range of a Google Spreadsheet. REQUIRES user review."
    args_schema = SheetsUpdateInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        sheet_id = args["spreadsheet_id"]
        range_name = args["range_name"]
        values = args["values"]
        
        decision = wingman_interrupt({
            "tool": "google_sheets_update",
            "prompt": f"Overwrite range '{range_name}' in spreadsheet?",
            "data": {
                "spreadsheet_id": sheet_id,
                "range_name": range_name,
                "values": values
            }
        }, context)
        
        if decision.get("approved", False) is True:
            final_values = decision.get("values", values)
            
            res = await google_sheets_service.update_range(sheet_id, final_values, range_name)
            
            # Synchronize overwritten state to semantic recall index
            await _sync_spreadsheet_to_memory(sheet_id, title=None, context=context)
            
            return {
                "status": "Range Updated Successfully",
                "spreadsheet_id": sheet_id,
                "updated_range": res.get("updated_range")
            }
        else:
            return {"status": "Update Cancelled", "reason": decision.get("reason", "Declined by human administrator.")}


# Tool 5: Search Spreadsheets (Safe)

class SheetsSearchInput(BaseModel):
    query: str = Field(..., description="Keywords to search for in spreadsheet titles.")
    max_results: int = Field(5, description="Number of results to return.")

class SheetsSearchTool(BaseWingmanTool):
    """
    Scans Google Drive specifically for Google Sheet assets. Safe utility.
    """
    name = "google_sheets_search"
    description = "Searches user's Google Drive specifically for matching Google Spreadsheets."
    args_schema = SheetsSearchInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        query = args["query"]
        max_res = args["max_results"]
        logger.info(f"[SheetsTool] Searching for spreadsheets matching: '{query}'")
        
        try:
            files = await google_sheets_service.search_spreadsheets(query, max_results=max_res)
            formatted = [
                {"id": f["id"], "name": f["name"], "link": f.get("webViewLink"), "modified": f.get("modifiedTime")}
                for f in files
            ]
            return {
                "success": True,
                "results": formatted,
                "summary": f"Located {len(formatted)} matching spreadsheets."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
