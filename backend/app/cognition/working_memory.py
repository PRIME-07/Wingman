from typing import List, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from backend.app.core.logging import logger
from backend.app.services.llm.client import get_llm
from backend.app.prompts.registry import prompt_registry
from backend.app.core.utils import extract_text_content

class WorkingMemoryCompiler:
    """
    Responsible for context optimization: filters, compresses, and budgets 
    the raw message context to prevent LLM reasoning degradation.
    """
    def __init__(self, rolling_buffer_size: int = 100, token_limit: int = 20000):
        # Default to last 100 messages (approx 50 turns)
        self.rolling_buffer_size = rolling_buffer_size
        self.token_limit = token_limit

    def _clean_incomplete_tool_sequences(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Detects and removes any AIMessages with tool_calls that lack a corresponding
        ToolMessage response, and prunes their orphan responses. This protects OpenAI
        invocations from collapsing if the graph has suspended in an intermediate state.
        """
        if not messages:
            return []
            
        # 1. Inventory all tool messages present in the context
        tool_response_ids = {
            m.tool_call_id for m in messages 
            if hasattr(m, "tool_call_id") and m.tool_call_id
        }
        
        # 2. Scan AIMessages to locate incomplete tool allocations
        to_remove_indices = set()
        for i, msg in enumerate(messages):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                # An AIMessage tool block is valid ONLY if every distinct call has a response
                is_complete = all(tc.get("id") in tool_response_ids for tc in msg.tool_calls)
                if not is_complete:
                    to_remove_indices.add(i)
                    # Also schedule any partial responses tied to this block for eviction
                    for tc in msg.tool_calls:
                        call_id = tc.get("id")
                        if call_id:
                            for j, candidate in enumerate(messages):
                                if hasattr(candidate, "tool_call_id") and candidate.tool_call_id == call_id:
                                    to_remove_indices.add(j)
                                    
        if not to_remove_indices:
            return messages
            
        cleaned = [m for i, m in enumerate(messages) if i not in to_remove_indices]
        logger.info(f"[Cognition] Pruned {len(to_remove_indices)} incomplete tool-execution messages from memory stack to maintain schema hygiene.")
        return cleaned

    async def compile_and_budget(self, messages: List[BaseMessage], current_summary: str) -> Tuple[List[BaseMessage], str, bool]:
        """
        Slices the messages to the active rolling buffer part.
        Returns (optimized_messages, updated_summary_string, was_updated_flag).
        Historical context beyond the window relies on Neo4j/RAG.
        """
        if not messages:
            return [], current_summary or "", False

        # Strip incomplete tool allocations (e.g., if suspended waiting for human approval)
        clean_messages = self._clean_incomplete_tool_sequences(messages)
        
        total_count = len(clean_messages)
        
        if total_count <= self.rolling_buffer_size:
            return clean_messages, current_summary or "", False
            
        # Fast, zero-cost slice of recent messages
        recent_messages = clean_messages[-self.rolling_buffer_size:]
        
        logger.debug(f"[Cognition] Fast-slicing working memory from {total_count} to {self.rolling_buffer_size} messages.")
        
        # We no longer perform expensive summarization. Long term facts are handled by Neo4j.
        return recent_messages, current_summary or "", False

# Single access provider
working_memory_compiler = WorkingMemoryCompiler()
