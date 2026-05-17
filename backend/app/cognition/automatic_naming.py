from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.memory.mongodb_client import mongo_client
from backend.app.services.llm.client import get_llm
from backend.app.core.logging import logger
from langchain_core.messages import HumanMessage

class AutomaticTitle(BaseModel):
    title: str = Field(description="Brief, premium title for the session (1-5 words max)")
    confidence: float = Field(description="Self-assessed confidence score from 0.0 to 1.0 indicating if the overall topic is clear")
    reasoning: str = Field(description="Explanation for the confidence level")

class AutomaticNamingEngine:
    """
    Priority 11: Automatically generates an initial conversational session name
    strictly after the first message exchange and persists it securely.
    """
    
    def __init__(self):
        self.trigger_turns = {1} # Trigger naming strictly after the first message pair
        
    async def evaluate_and_refine(self, session_id: str):
        """
        Loads the current conversation logs, assesses turn count, and computes 
        a higher-quality session title if the initial trigger interval is reached.
        """
        if not session_id:
            return
            
        # 1. Fetch messages to evaluate length
        messages = await mongo_client.get_session_conversations(session_id, limit=30)
        user_messages = [m for m in messages if m.get("role") == "user" or m.get("type") == "human"]
        turn_count = len(user_messages)
        
        # Standard interval gating to avoid redundant LLM invocations
        if turn_count not in self.trigger_turns:
            return
            
        logger.info(f"[AutomaticNaming] Trigger hit at turn {turn_count} for Session={session_id}. Reviewing title...")
        
        # 2. Retrieve current state
        session = await mongo_client.get_session(session_id)
        if not session:
            return
            
        metadata = session.get("metadata", {})
        current_conf = metadata.get("naming_confidence", 0.0)
        current_title = session.get("session_name", "")
        
        # 3. Run LLM critique
        history_preview = []
        for msg in messages[-10:]: # Tail end of conversation
            content = msg.get("content", "")[:300]
            role = msg.get("role", "unknown").upper()
            history_preview.append(f"[{role}] {content}")
            
        preview_str = "\n".join(history_preview)
        
        prompt = f"""
Analyze this recent chat history between a user and an AI.
Synthesize a precise, concise, and premium topic title (1 to 5 words maximum).
Also provide a confidence score from 0.0 to 1.0 indicating how clear the OVERALL goal/subject of this entire session is.
If the chat consists only of brief greetings, set confidence low. If a clear task or question is established, set confidence high.

[RECENT CHAT DIALOGUE]
{preview_str}

[CURRENT ASSIGNED TITLE]
{current_title} (Current Confidence: {current_conf})
"""

        try:
            from backend.app.core.config import settings
            raw_llm = await get_llm(model_name=settings.FAST_MODEL, temperature=0.2, reasoning_effort="low")
            llm = raw_llm.with_structured_output(AutomaticTitle)
            result: AutomaticTitle = await llm.ainvoke([HumanMessage(content=prompt)])
            
            logger.info(
                f"[AutomaticNaming] Evaluated Candidate='{result.title}' [Conf={result.confidence:.2f}] "
                f"vs Current='{current_title}' [Conf={current_conf:.2f}]"
            )
            
            # Gating Policy: Commit if upgrading from default, OR is absolute highly confident (> 0.85)
            is_default = current_title == "New Conversation"
            is_upgrade = is_default or (result.confidence >= 0.85 and result.title != current_title)
            
            if is_upgrade:
                logger.info(f"[AutomaticNaming] UPGRADING session name to: '{result.title}'")
                
                # Update metadata
                metadata["naming_confidence"] = result.confidence
                metadata["naming_turn"] = turn_count
                
                # Persistent updates
                mongo_client.connect()
                from datetime import datetime
                await mongo_client.db["sessions"].update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "session_name": result.title,
                            "metadata": metadata,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

                
        except Exception as e:
            logger.error(f"[AutomaticNaming] Title generation failed: {e}")

# Singleton Engine
automatic_naming_engine = AutomaticNamingEngine()
