import uuid
from typing import List, Dict, Any
from backend.app.core.logging import logger
from backend.app.memory.mongodb_client import mongo_client
from backend.app.memory.vector_client import chroma_client
from backend.app.services.documents.parser import document_parser
from backend.app.services.documents.processor import document_processor
from backend.app.event_bus.bus import event_bus
from backend.app.telemetry.schemas import TelemetryEvent, TelemetryEventType

class DocumentManager:
    """
    High-level coordinator managing multi-format parsing, vector-embedding generation,
    and dual-stage registry indexing (Metadata in Mongo, Vectors in Pinecone).
    """
    
    @staticmethod
    async def ingest_document(file_bytes: bytes, filename: str, session_id: str = None) -> Dict[str, Any]:
        """
        Runs the full RAG Ingestion Pipeline for an uploaded user document.
        
        :param file_bytes: Raw byte stream from file upload.
        :param filename: Original user filename.
        :param session_id: Optional session ID association.
        """
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        trace_id = f"tr-{uuid.uuid4().hex[:8]}"
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        
        logger.info(f"[Doc-Manager] Spawning ingestion runtime for {filename} | Assigning ID: {doc_id}")
        
        async def report_progress(percent: int, stage: str):
            await event_bus.publish("telemetry", TelemetryEvent(
                event_type=TelemetryEventType.DOC_INGEST_PROGRESS,
                trace_id=trace_id,
                run_id=run_id,
                payload={
                    "filename": filename,
                    "progress": percent,
                    "stage": stage
                }
            ))

        try:
            # 1. Extract clean textual representations
            await report_progress(25, "Parsing Document Structure...")
            text = await document_parser.parse_file(file_bytes, filename)
            
            # 2. Break monolithic text into 150-token overlapped chunks for high-resolution semantic search
            await report_progress(50, "Segmenting Semantic Chunks...")
            chunks = document_processor.process_document(
                text=text,
                doc_id=doc_id,
                filename=filename,
                chunk_tokens=150,
                char_overlap=150
            )
            
            if not chunks:
                raise ValueError("Parsed document returned zero characters or token segments.")
                
            # 3. Commit Dense Vector Representation directly to Chroma
            await report_progress(75, "Vectorizing Neural Index...")
            logger.info(f"[Doc-Manager] Dispatching {len(chunks)} chunks to the Chroma vector engine...")
            vector_success = await chroma_client.upsert_chunks(chunks)
            
            if not vector_success:
                raise RuntimeError("Vector Storage Upsert failed. Semantic memory index may be unreachable.")
                
            # 4. Register Document Ownership & Metrics in the Main System Catalog (MongoDB)
            await report_progress(100, "Finalizing Vault Registration...")
            meta_payload = await mongo_client.save_document_metadata(
                doc_id=doc_id,
                filename=filename,
                file_size=len(file_bytes),
                chunk_count=len(chunks),
                session_id=session_id,
                metadata={
                    "total_tokens_est": sum(c["metadata"]["tokens"] for c in chunks)
                }
            )
            
            logger.info(f"[Doc-Manager] Document {filename} indexed SUCCESSFULLY. Registry updated.")
            return {
                "success": True,
                "doc_id": doc_id,
                "filename": filename,
                "chunks": len(chunks),
                "metadata": meta_payload
            }
            
        except Exception as e:
            logger.error(f"[Doc-Manager] CRITICAL PIPELINE ABORT during '{filename}': {e}", exc_info=True)
            # Re-raise for upstream API responders to wrap in Clean HTTP 500/400 exceptions
            raise

    @staticmethod
    async def ingest_virtual_asset(
        asset_id: str,
        title: str,
        content: str,
        asset_type: str,
        session_id: str = None,
        url: str = None
    ) -> Dict[str, Any]:
        """
        Ingests or re-ingests high-level virtual assets (e.g., Google Docs, Sheets, etc.)
        into Pinecone vector memory and MongoDB relational storage.
        Uses a 'Prune-then-Ingest' strategy to replace existing indices atomically.
        """
        # 1. Establish canonical tracking key
        doc_id = f"virt_{asset_id}"
        logger.info(f"[Doc-Manager] Syncing virtual asset '{title}' ({asset_type}) with doc_id: {doc_id}")
        
        try:
            # 2. Prune any historical vector footprint to prevent duplicate drift
            logger.debug(f"[Doc-Manager] Flushing historical indices for {doc_id} before fresh write...")
            await chroma_client.delete_by_document_id(doc_id)
            
            # 3. Chunk complete current state into granular, overlapping chunks
            chunks = document_processor.process_document(
                text=content,
                doc_id=doc_id,
                filename=title,
                chunk_tokens=150,
                char_overlap=150
            )
            
            if not chunks:
                logger.warning(f"[Doc-Manager] Virtual asset {title} holds zero processable text contents. Clearing indexes only.")
                await mongo_client.delete_document_metadata(doc_id)
                return {"success": True, "chunks": 0, "cleared": True}

            # 4. Add tracking tags to vector metadata
            for c in chunks:
                c["metadata"].update({
                    "asset_type": asset_type,
                    "virtual": True,
                    "url": url or ""
                })
            
            # 5. Batch ingest into vector database
            vector_success = await chroma_client.upsert_chunks(chunks)
            if not vector_success:
                raise RuntimeError("Vector Database rejected upsert payload.")
            
            # 6. Overwrite MongoDB registry
            meta_payload = await mongo_client.save_document_metadata(
                doc_id=doc_id,
                filename=title,
                file_size=len(content),
                chunk_count=len(chunks),
                session_id=session_id,
                metadata={
                    "asset_type": asset_type,
                    "url": url,
                    "virtual": True,
                    "total_tokens_est": sum(c["metadata"].get("tokens", 0) for c in chunks)
                }
            )
            
            logger.info(f"[Doc-Manager] Virtual asset '{title}' successfully synchronized.")
            return {
                "success": True,
                "doc_id": doc_id,
                "filename": title,
                "chunks": len(chunks),
                "metadata": meta_payload
            }
            
        except Exception as e:
            logger.error(f"[Doc-Manager] CRITICAL SYNC FAILURE during '{title}': {e}", exc_info=True)
            raise

    @staticmethod
    async def purge_document(doc_id: str) -> bool:
        """
        Permanently removes a document both from semantic memory and relational catalogs.
        """
        logger.warning(f"[Doc-Manager] Purging document indexes for ID: {doc_id}")
        
        # 1. Clean vector space first
        vector_success = await chroma_client.delete_by_document_id(doc_id)
        
        # 2. Remove catalog registry entry
        mongo_success = await mongo_client.delete_document_metadata(doc_id)
        
        logger.info(f"[Doc-Manager] Purge status for {doc_id}: Vector={vector_success}, Registry={mongo_success}")
        return vector_success and mongo_success

# Functional Export
document_manager = DocumentManager()
