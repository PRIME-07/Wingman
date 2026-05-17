import uuid
import asyncio
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from fastembed import TextEmbedding
from backend.app.core.config import settings
from backend.app.core.logging import logger

class ChromaVectorClient:
    """
    Unified client managing semantic indexing and retrieval via ChromaDB locally.
    Uses fastembed for high-performance local embeddings generation.
    """
    def __init__(self):
        self._client = None
        self._collection = None
        self._embedding_model = None
        
    def _get_embedding_model(self):
        """Lazy load the fastembed model to avoid blocking on startup."""
        if self._embedding_model is None:
            logger.info(f"[Chroma-Vector] Loading local embedding model: {settings.CHROMA_EMBEDDING_MODEL}")
            self._embedding_model = TextEmbedding(model_name=settings.CHROMA_EMBEDDING_MODEL)
        return self._embedding_model

    def _get_client(self):
        """Lazy-loads the ChromaDB client."""
        if self._client is None:
            server_url = settings.CHROMA_SERVER_URL
            if server_url:
                host = server_url.replace("http://", "").replace("https://", "").split(":")[0]
                port = server_url.split(":")[-1] if ":" in server_url.replace("http://", "") else "8000"
                self._client = chromadb.HttpClient(host=host, port=port, settings=ChromaSettings(allow_reset=True))
                logger.info(f"[Chroma-Vector] Connected to ChromaDB HttpClient at {server_url}")
            else:
                self._client = chromadb.Client()
                logger.info("[Chroma-Vector] Initialized ephemeral/local ChromaDB client.")
        return self._client

    def _get_collection(self):
        """Retrieves or creates the target collection."""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"[Chroma-Vector] Collection '{settings.CHROMA_COLLECTION_NAME}' ready.")
        return self._collection

    async def embed_texts(self, texts: List[str], input_type: str = "passage") -> List[List[float]]:
        """
        Generates dense vector embeddings asynchronously using local fastembed.
        """
        if not texts:
            return []
            
        logger.debug(f"[Chroma-Vector] Generating {len(texts)} embeddings | Model={settings.CHROMA_EMBEDDING_MODEL} | Type={input_type}")
        try:
            model = self._get_embedding_model()
            # Fastembed returns a generator of numpy arrays, convert to lists of floats
            embeddings_gen = model.embed(texts)
            embeddings = [e.tolist() for e in embeddings_gen]
            return embeddings
        except Exception as e:
            logger.error(f"[Chroma-Vector] Critical inference generation crash: {e}", exc_info=True)
            raise

    async def upsert_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        Encodes text payloads and performs bulk upsert operations to ChromaDB.
        """
        if not chunks:
            return True
            
        try:
            collection = self._get_collection()
            
            # 1. Extract raw texts and generate dense representations
            texts = [c["text"] for c in chunks]
            vectors = await self.embed_texts(texts, input_type="passage")
            
            # 2. Re-construct payload format for Chroma
            ids = []
            metadatas = []
            documents = []
            
            for i, vector in enumerate(vectors):
                c = chunks[i]
                chunk_id = c.get("id") or str(uuid.uuid4())
                meta = c.get("metadata") or {}
                
                # Chroma doesn't allow None or complex dicts in metadata
                clean_meta = {}
                for k, v in meta.items():
                    if v is not None and isinstance(v, (str, int, float, bool)):
                        clean_meta[k] = v
                    elif v is not None:
                         clean_meta[k] = str(v)
                         
                ids.append(chunk_id)
                metadatas.append(clean_meta)
                documents.append(c["text"])
            
            # 3. Upsert into ChromaDB
            logger.info(f"[Chroma-Vector] Shipping bulk batch of {len(ids)} records to collection...")
            collection.upsert(
                ids=ids,
                embeddings=vectors,
                metadatas=metadatas,
                documents=documents
            )
                
            logger.info(f"[Chroma-Vector] Upsert operations finalized. Indexed count: {len(ids)}.")
            return True
        except Exception as e:
            logger.error(f"[Chroma-Vector] Batch upsert flow aborted: {e}", exc_info=True)
            return False

    async def query_semantic_chunks(self, query: str, top_k: int = 5, filter: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Executes semantic similarity queries returning highly relevant segments.
        """
        try:
            collection = self._get_collection()
            
            # 1. Compute query representation
            vectors = await self.embed_texts([query], input_type="query")
            query_vector = vectors[0]
            
            # 2. Dispatch similarity lookup
            logger.debug(f"[Chroma-Vector] Executing search for query: '{query[:40]}...' | TopK={top_k}")
            res = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=filter if filter else None,
                include=["metadatas", "documents", "distances"]
            )
            
            # 3. Deserialize matches
            matches = []
            if res['ids'] and len(res['ids']) > 0:
                for i in range(len(res['ids'][0])):
                    match_id = res['ids'][0][i]
                    # Convert distance to a similarity score (approximate for cosine)
                    distance = res['distances'][0][i] if 'distances' in res and res['distances'] else 0.0
                    score = max(0.0, 1.0 - distance)
                    
                    document = res['documents'][0][i] if 'documents' in res and res['documents'] else ""
                    metadata = res['metadatas'][0][i] if 'metadatas' in res and res['metadatas'] else {}
                    
                    matches.append({
                        "id": match_id,
                        "score": score,
                        "text": document,
                        "metadata": metadata
                    })
                
            logger.info(f"[Chroma-Vector] Search finalized. Found {len(matches)} matching records.")
            return matches
        except Exception as e:
            logger.error(f"[Chroma-Vector] Search query crashed: {e}", exc_info=True)
            return []

    async def delete_by_document_id(self, doc_id: str) -> bool:
        """
        Purges all vector records tagged with a specific document ID.
        """
        try:
            collection = self._get_collection()
            logger.info(f"[Chroma-Vector] Deleting all vectors with doc_id='{doc_id}'...")
            collection.delete(where={"doc_id": doc_id})
            logger.info(f"[Chroma-Vector] Deletion request finalized for doc_id='{doc_id}'.")
            return True
        except Exception as e:
            logger.error(f"[Chroma-Vector] Vector deletion failed: {e}", exc_info=True)
            return False

# Global instance export
chroma_client = ChromaVectorClient()
# Alias for backwards compatibility in existing imports
pinecone_client = chroma_client
