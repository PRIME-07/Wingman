from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import List, Dict, Any, Optional
from backend.app.services.documents.manager import document_manager
from backend.app.services.google.docs import google_docs_service
from backend.app.services.google.sheets import google_sheets_service
from backend.app.memory.mongodb_client import mongo_client
from backend.app.core.logging import logger

router = APIRouter()

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_and_index_document(file: UploadFile = File(...), session_id: Optional[str] = Form(None)):
    """
    Primary Ingestion Pipe: Receives raw document file, strips formatting,
    tokenizes into segments, and indexes semantically via Pinecone Inference.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source filename missing.")

    logger.info(f"[API-Doc] Post request encountered for upload: '{file.filename}'")
    
    try:
        # 1. Read file directly to in-memory bytes to avoid transient filesystem disk locks
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file content is zero bytes.")
            
        # 2. Dispatch to processing coordinator
        result = await document_manager.ingest_document(file_bytes=content, filename=file.filename, session_id=session_id)
        return result
        
    except ValueError as ve:
        # Caught formats parsing or structural failures
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))
    except Exception as e:
        # System crashes, rate limits, vector engine network issues
        logger.error(f"[API-Doc] Internal fault during document indexing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document pipeline aborted: {str(e)}"
        )
    finally:
        await file.close()

@router.get("", response_model=List[Dict[str, Any]])
async def get_uploaded_documents_catalog(limit: int = 100):
    """
    Fetches the registered catalog list of all successfully vectorized user documents.
    """
    try:
        docs = await mongo_client.list_documents(limit=limit)
        # Transform Mongo _id object for JSON serialization safely
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            if "uploaded_at" in doc:
                doc["uploaded_at"] = doc["uploaded_at"].isoformat()
        return docs
    except Exception as e:
        logger.error(f"[API-Doc] Failed retrieving document catalog: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Registry query failure."
        )

@router.delete("/{doc_id}")
async def purge_document_records(doc_id: str):
    """
    Permanently erases document indices from the knowledge retrieval network.
    """
    try:
        success = await document_manager.purge_document(doc_id)
        if not success:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document ID not located.")
             
        return {"success": True, "message": f"Successfully wiped record {doc_id} from system space."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API-Doc] Critical purge exception for ID={doc_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed completing wipe pipeline: {str(e)}"
        )

@router.post("/sync")
async def sync_remote_asset(payload: Dict[str, Any]):
    """
    On-demand semantic synchronization for Google Workspace assets.
    """
    asset_id = payload.get("asset_id")
    asset_type = payload.get("asset_type") # 'google_doc' or 'google_sheet'
    title = payload.get("title", "Unnamed Workspace Asset")
    session_id = payload.get("session_id")

    if not asset_id or not asset_type:
        raise HTTPException(status_code=400, detail="asset_id and asset_type are required.")

    try:
        content = ""
        url = ""
        
        if asset_type == "google_doc":
            doc_res = await google_docs_service.read_document(asset_id)
            content = doc_res.get("content", "")
            title = doc_res.get("title", title)
            url = f"https://docs.google.com/document/d/{asset_id}/edit"
        elif asset_type == "google_sheet":
            sheet_res = await google_sheets_service.read_spreadsheet(asset_id)
            values = sheet_res.get("values", [])
            # Simple tabular serialization
            lines = []
            for row in values:
                lines.append(" | ".join([str(c) if c is not None else "" for c in row]))
            content = "\n".join(lines)
            title = await google_sheets_service.get_spreadsheet_title(asset_id)
            url = f"https://docs.google.com/spreadsheets/d/{asset_id}/edit"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported asset type: {asset_type}")

        # Dispatch to RAG manager
        result = await document_manager.ingest_virtual_asset(
            asset_id=asset_id,
            title=title,
            content=content,
            asset_type=asset_type,
            session_id=session_id,
            url=url
        )
        return result
    except Exception as e:
        logger.error(f"[API-Doc] Sync failed for {asset_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
