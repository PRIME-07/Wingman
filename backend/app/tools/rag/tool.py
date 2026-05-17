from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext
from backend.app.memory.vector_client import chroma_client
from backend.app.core.logging import logger

class DocumentRAGInput(BaseModel):
    query: str = Field(..., description="The semantic question or concept to lookup within the user's uploaded documents corpus.")
    top_k: int = Field(default=5, description="Maximum number of relevant snippets/chunks to retrieve. Ranges 1-10.")
    document_id: Optional[str] = Field(default=None, description="Optional: Restrict the retrieval sweep to a specific document hash if known.")

class DocumentRAGTool(BaseWingmanTool):
    """
    Allows the Planner to traverse across user-provided knowledge reservoirs (PDFs, DOCX, Markdown)
    and inject high-fidelity vector snippets as conversational context grounding.
    """
    name = "document_rag_query"
    description = (
        "Executes a deep semantic lookup across all user-uploaded document files "
        "(e.g., PDF instruction sets, legal DOCX files) and system-generated digital assets "
        "(e.g., Google Docs, Sheets). Use this whenever the user references uploaded files, "
        "created assets, or asks questions regarding persistent custom knowledge."
    )
    args_schema = DocumentRAGInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        query = args["query"]
        top_k = min(max(args.get("top_k", 5), 1), 10)
        doc_id = args.get("document_id")

        logger.info(f"[RAG-Tool] Invoking Vector Search | Query: '{query[:50]}...' | FilterDoc={doc_id}")
        
        # 1. Setup dynamic metadata filter if restricted to single doc
        search_filter = None
        if doc_id:
            search_filter = {"doc_id": doc_id}

        try:
            # 2. Execute vector similarity match via Chroma client
            matches = await chroma_client.query_semantic_chunks(
                query=query,
                top_k=top_k,
                filter=search_filter
            )
            
            if not matches:
                logger.info("[RAG-Tool] Retrieval completed with ZERO matches.")
                return {
                    "success": True,
                    "matches_found": 0,
                    "results": [],
                    "guidance": "No matching content found in the documents. The user may not have uploaded this specific context yet."
                }
                
            # 3. Structure and clean results for LLM consumption
            extracted_results = []
            for item in matches:
                meta = item.get("metadata", {})
                extracted_results.append({
                    "score": round(item["score"], 4),
                    "source_file": meta.get("filename", "Unknown Source"),
                    "chunk_seq": meta.get("sequence"),
                    "content": item["text"]
                })
                
            logger.info(f"[RAG-Tool] Successfully pulled {len(extracted_results)} contexts.")
            
            return {
                "success": True,
                "matches_found": len(extracted_results),
                "results": extracted_results
            }
            
        except Exception as e:
            logger.error(f"[RAG-Tool] Vector retrieval process faulted: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"RAG Engine failure: {str(e)}",
                "guidance": "The ChromaDB vector service is unreachable. Ensure the docker container is running."
            }
