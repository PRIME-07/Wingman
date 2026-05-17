from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext, wingman_interrupt
from backend.app.core.logging import logger
from backend.app.services.google.docs import google_docs_service

# Tool 1: Document Create (Requires HITL)

class DocsCreateInput(BaseModel):
    title: str = Field(..., description="Desired title for the new Google Document.")

class DocsCreateTool(BaseWingmanTool):
    """
    Instantiates a blank Google Doc. Operates under HITL clearance
    to prevent agentic file system pollution.
    """
    name = "google_docs_create"
    description = "Creates a new empty Google Document in Drive. REQUIRES human clearance."
    args_schema = DocsCreateInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        title = args["title"]
        
        logger.info(f"[DocsTool] Prompting confirmation for document creation: '{title}'")
        
        # LangGraph Interrupt for safety
        decision = wingman_interrupt({
            "tool": "google_docs_create",
            "prompt": f"Create document titled '{title}'?",
            "data": {"title": title}
        }, context)
        
        if decision.get("approved", False) is True:
            result = await google_docs_service.create_document(title)
            
            # Schedule semantic indexing hook
            try:
                from backend.app.services.documents.manager import document_manager
                await document_manager.ingest_virtual_asset(
                    asset_id=result["document_id"],
                    title=title,
                    content="",  # Starts empty
                    asset_type="google_doc",
                    session_id=context.metadata.get("session_id"),
                    url=result["url"]
                )
                logger.info(f"[DocsTool] Registered empty virtual document {result['document_id']} in indexing space.")
            except Exception as sync_err:
                logger.warning(f"[DocsTool] Non-fatal initial doc register issue: {sync_err}")

            return {
                "status": "Created Successfully",
                "document_id": result["document_id"],
                "url": result["url"]
            }
        else:
            return {"status": "Cancelled", "reason": decision.get("reason", "Operator aborted write.")}


# Tool 2: Read Document (Safe)

class DocsReadInput(BaseModel):
    document_id: str = Field(..., description="Google Document Unique ID (from URL or search tool).")

class DocsReadTool(BaseWingmanTool):
    """
    Extracts contents from a document.
    Enables ingestion of persistent data contexts directly into the prompt context.
    """
    name = "google_docs_read"
    description = "Reads and extracts the text content of a specific Google Document."
    args_schema = DocsReadInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        doc_id = args["document_id"]
        logger.info(f"[DocsTool] Triggering read operation for DocID={doc_id}")
        
        try:
            content_res = await google_docs_service.read_document(doc_id)
            
            # Background semantic memory sync on read: keeps vector store
            # fresh even if the user edits manually in the browser!
            try:
                from backend.app.services.documents.manager import document_manager
                await document_manager.ingest_virtual_asset(
                    asset_id=doc_id,
                    title=content_res.get("title", "Unnamed Document"),
                    content=content_res.get("content", ""),
                    asset_type="google_doc",
                    session_id=context.metadata.get("session_id"),
                    url=f"https://docs.google.com/document/d/{doc_id}/edit"
                )
                logger.info(f"[DocsTool] Proactively sync'd read content for doc {doc_id} in semantic memory.")
            except Exception as sync_err:
                logger.warning(f"[DocsTool] Proactive RAG-sync on read failed: {sync_err}")

            return {
                "success": True,
                "title": content_res["title"],
                "content": content_res["content"]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# Tool 3: Edit Document (Requires HITL)

class DocsEditInput(BaseModel):
    document_id: str = Field(..., description="Google Document ID to edit.")
    text_to_append: str = Field(..., description="Plain-text contents to append to the document's end.")

class DocsEditTool(BaseWingmanTool):
    """
    Appends content to an existing Google Doc. Enforced by
    HITL validation to ensure the appended content is correct.
    """
    name = "google_docs_edit"
    description = "Appends new content to the end of a Google Document. REQUIRES user review."
    args_schema = DocsEditInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        doc_id = args["document_id"]
        text = args["text_to_append"]
        
        decision = wingman_interrupt({
            "tool": "google_docs_edit",
            "prompt": f"Append content to document?",
            "data": {
                "document_id": doc_id,
                "text_to_append": text
            }
        }, context)
        
        if decision.get("approved", False) is True:
            # Apply manual revisions if overridden in payload
            final_text = decision.get("text_to_append", text)
            
            await google_docs_service.append_text(doc_id, final_text)
            
            # Continuous Re-indexing Strategy: Prune and Ingest fresh copy
            try:
                from backend.app.services.documents.manager import document_manager
                fresh_doc = await google_docs_service.read_document(doc_id)
                await document_manager.ingest_virtual_asset(
                    asset_id=doc_id,
                    title=fresh_doc.get("title", "Unnamed Document"),
                    content=fresh_doc.get("content", ""),
                    asset_type="google_doc",
                    session_id=context.metadata.get("session_id"),
                    url=f"https://docs.google.com/document/d/{doc_id}/edit"
                )
                logger.info(f"[DocsTool] Atomic vector re-indexing completed for doc {doc_id}.")
            except Exception as sync_err:
                logger.warning(f"[DocsTool] RAG-sync post-append failed: {sync_err}")

            return {"status": "Content Appended Successfully", "document_id": doc_id}
        else:
            return {"status": "Edit Cancelled", "reason": decision.get("reason", "Declined.")}


# Tool 4: Search Documents (Safe)

class DocsSearchInput(BaseModel):
    query: str = Field(..., description="Keywords to search for in document titles.")
    max_results: int = Field(5, description="Number of results to return.")

class DocsSearchTool(BaseWingmanTool):
    """
    Leverages Google Drive endpoint scanning to discover Google Docs matching titles.
    Allows Wingman to independently locate and access persistent workspace assets.
    """
    name = "google_docs_search"
    description = "Searches the user's Google Drive specifically for matching Google Documents."
    args_schema = DocsSearchInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        query = args["query"]
        logger.info(f"[DocsTool] Searching for keywords: '{query}'")
        
        try:
            files = await google_docs_service.search_documents(query, max_results=args["max_results"])
            formatted = [
                {"id": f["id"], "name": f["name"], "link": f.get("webViewLink"), "modified": f.get("modifiedTime")}
                for f in files
            ]
            return {
                "success": True,
                "results": formatted,
                "summary": f"Located {len(formatted)} matching documents."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
