import json
from datetime import datetime, timedelta
from typing import List
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.prompts import ChatPromptTemplate
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.services.llm.client import get_llm
from backend.app.memory.mongodb_client import mongo_client
from backend.app.memory.neo4j_client import neo4j_client
from backend.app.prompts.registry import prompt_registry

class SemanticFact(BaseModel):
    """Structured fact representation for the Neo4j semantic layer."""
    model_config = ConfigDict(extra="forbid")

    entity: str = Field(description="The main entity or topic name, e.g., 'Coffee', 'Alice', 'Wingman Project'.")
    type: str = Field(description="The category of knowledge: Preference, Person, Project, Task, General.")
    fact: str = Field(description="The specific piece of information or preference learned about the entity.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0 based on explicitly stated user facts.")

class KnowledgeDistillationResult(BaseModel):
    """Container for a collection of distilled knowledge nodes."""
    model_config = ConfigDict(extra="forbid")

    memories: List[SemanticFact] = Field(description="List of semantic facts learned from the logs. Use empty list if none.")

async def run_micro_consolidation(max_retries: int = 3) -> bool:
    """
    Executes the central memory lifecycle dynamically:
    MongoDB Logs -> LLM Distillation -> Neo4j Transaction -> Advance Clock.
    
    Enforces strict verification checks before ever advancing.
    """
    now = datetime.utcnow()
    
    # Identify processing window from the database
    last_log = await mongo_client.get_last_consolidation_log()
    
    if last_log and "processed_until_timestamp" in last_log:
        start_time = last_log["processed_until_timestamp"]
    else:
        # Genesis run: fall back to 1 day ago
        start_time = now - timedelta(days=1)
        
    end_time = now
    
    logger.info(f"[Consolidation] Starting micro-batch pipeline: {start_time.isoformat()} -> {end_time.isoformat()}")
    
    try:
        # Step 1: Fetch raw chat context from active window
        raw_logs = await mongo_client.get_conversations_between(start_time, end_time)
        if not raw_logs:
            logger.info(f"[Consolidation] No conversations found in window. Terminating cycle cleanly.")
            # Record empty execution to advance the clock
            await mongo_client.record_consolidation(now, end_time, 0)
            return True
            
        # Format message list to human-readable block for LLM prompt
        formatted_logs = []
        for msg in raw_logs:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted_logs.append(f"[{role.upper()}]: {content}")
            
        conversation_block = "\n".join(formatted_logs)
        logger.debug(f"[Consolidation] Loaded {len(raw_logs)} raw message turns for context.")

        # Step 2: LLM Distillation using structured schemas
        llm = await get_llm()
        # Use with_structured_output for absolute parsing reliability
        structured_llm = llm.with_structured_output(KnowledgeDistillationResult)
        
        consolidation_prompt = prompt_registry.get_prompt("memory_consolidation")
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a cognitive memory distiller specializing in building clean user-profiles and permanent graph-relations."),
            ("human", consolidation_prompt)
        ])
        
        chain = prompt_template | structured_llm
        
        logger.info(f"[Consolidation] Dispatching {len(conversation_block)} characters to {settings.OPENAI_MODEL} for distillation...")
        distillation_results: KnowledgeDistillationResult = await chain.ainvoke({"conversation_log": conversation_block})
        
        if not distillation_results or not distillation_results.memories:
            logger.info(f"[Consolidation] LLM extracted 0 new semantic insights. Retaining raw logs and advancing clock.")
            await mongo_client.record_consolidation(now, end_time, len(raw_logs))
            return True
            
        logger.info(f"[Consolidation] Distillation successful. Extracted {len(distillation_results.memories)} permanent semantic nodes.")
        
        # Convert pydantic outputs into native dictionary array for Neo4j engine
        memory_records = [mem.model_dump() for mem in distillation_results.memories]
        
        # Step 3: Safe commit to the Permanent Semantic Neo4j DB
        write_success = False
        for attempt in range(1, max_retries + 1):
            logger.info(f"[Consolidation] Writing to Neo4j (Attempt {attempt}/{max_retries})...")
            write_success = neo4j_client.save_semantic_memories(memory_records)
            if write_success:
                logger.info(f"[Consolidation] Neo4j write transaction COMMITTED SUCCESSFULLY.")
                break
            else:
                logger.warning(f"[Consolidation] Write attempt {attempt} FAILED. Retrying...")
                
        # Step 4: Safety Safeguards. DO NOT PRUNE IF TRANSACTION FAILS!
        if not write_success:
            logger.critical(f"[Consolidation-SAFETY] Neo4j transaction FAILED after {max_retries} attempts.")
            logger.critical(f"[Consolidation-SAFETY] PRESERVING raw MongoDB logs for window to prevent cognitive data-loss.")
            return False
            
        # Step 5: Transaction and confirmation succeeded. Retain all chats and advance consolidation clock.
        logger.info(f"[Consolidation] Permanent semantic facts recorded. Retaining raw chat logs in working collection.")
        await mongo_client.record_consolidation(now, end_time, len(raw_logs))
        
        # Priority 13: Adaptive Memory Lifecycle
        # Execute decay algorithms to age out stale facts and archive weak references.
        logger.info("[Consolidation] Triggering programmatic memory decay routine...")
        decay_stats = neo4j_client.run_decay_lifecycle(decay_factor=0.85, archive_threshold=0.4)
        logger.info(f"[Consolidation] Adaptive maintenance finished: Decay={decay_stats['decayed']} Archive={decay_stats['archived']}")
        
        logger.info(f"[Consolidation] Micro-batch Lifecycle completed flawlessly! 🎉")
        return True

    except Exception as e:
        logger.error(f"[Consolidation-ERROR] Catastrophic execution failure: {e}", exc_info=True)
        logger.error(f"[Consolidation-SAFETY] ABORTED lifecycle. MongoDB data retained securely.")
        return False
