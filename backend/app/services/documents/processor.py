import uuid
import tiktoken
from typing import List, Dict, Any
from backend.app.core.logging import logger

class DocumentProcessor:
    """
    Converts monolithic text blobs into optimized, sized, and context-retaining
    chunks suitable for vectorization via the Pinecone inference API.
    """
    def __init__(self):
        # Initialize cl100k_base (OpenAI standard) tokenizer
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
            logger.info("[Doc-Processor] TikToken tokenizer loaded successfully.")
        except Exception as e:
            logger.error(f"[Doc-Processor] Failed retrieving encoding cl100k_base: {e}")
            self.tokenizer = tiktoken.encoding_for_model("gpt-4")

    def process_document(
        self, 
        text: str, 
        doc_id: str, 
        filename: str, 
        chunk_tokens: int = 150, 
        char_overlap: int = 150
    ) -> List[Dict[str, Any]]:
        """
        Deconstructs raw document text and maps it to vectorized metadata chunks.
        
        :param text: Massive raw parsed document string.
        :param doc_id: Permanent unique ID linking chunks to source registry.
        :param filename: Label of original file source.
        :param chunk_tokens: Max tokens per chunk (default 300).
        :param char_overlap: Character boundaries to duplicate for context (default 60).
        """
        if not text or not text.strip():
            return []

        # 1. Break text into primary token units
        tokens = self.tokenizer.encode(text)
        logger.info(f"[Doc-Processor] Segmenting document | Tokens: {len(tokens)} | TargetSize: {chunk_tokens}")

        chunks = []
        token_index = 0
        chunk_seq = 0

        while token_index < len(tokens):
            # a. Pull primary token sequence
            primary_tokens = tokens[token_index : token_index + chunk_tokens]
            raw_chunk_text = self.tokenizer.decode(primary_tokens)
            
            # b. Apply precise overlap boundaries from PREVIOUS chunk dynamically
            overlap_prefix = ""
            if token_index > 0 and char_overlap > 0:
                # Dynamically calculate backtrack count based on requested overlap (roughly 3 chars/token + safety margin)
                backtrack_tokens = max(30, int(char_overlap / 3) + 15)
                backtrack_start = max(0, token_index - backtrack_tokens)
                prior_slice = tokens[backtrack_start:token_index]
                prior_text = self.tokenizer.decode(prior_slice)
                
                if len(prior_text) >= char_overlap:
                    overlap_prefix = prior_text[-char_overlap:]
                else:
                    overlap_prefix = prior_text
                    
            # Combine to build contextually enriched final string payload
            final_chunk_text = f"{overlap_prefix} {raw_chunk_text}".strip() if overlap_prefix else raw_chunk_text.strip()
            
            # c. Package Chunk Payload with structural metadata
            chunk_id = f"{doc_id}_c{chunk_seq}"
            chunks.append({
                "id": chunk_id,
                "text": final_chunk_text,
                "metadata": {
                    "doc_id": doc_id,
                    "filename": filename,
                    "sequence": chunk_seq,
                    "tokens": len(primary_tokens)
                }
            })

            # d. Progress primary scanner index (Non-overlapping steps in Token-space)
            token_index += chunk_tokens
            chunk_seq += 1

        logger.info(f"[Doc-Processor] Extracted {len(chunks)} sequential chunks from '{filename}'.")
        return chunks

# Functional Export
document_processor = DocumentProcessor()
