import re
from typing import Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from backend.app.core.logging import logger
from backend.app.services.llm.client import get_llm
from langchain_core.prompts import ChatPromptTemplate

class VerificationOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    verified: bool = Field(description="Does the source trace support this statement without hallucination?")
    confidence_adjustment: float = Field(description="Adjusted confidence score from 0.0 to 1.0.")
    justification: str = Field(description="Concise factual justification pointing to explicit log items.")

class MemoryGroundingVerifier:
    """
    Rigorous anti-hallucination gateway verifying candidate semantic memories 
    against immediate execution trace logs and tool outputs.
    """

    def __init__(self):
        self._llm = None
        self._structured_llm = None
        
    async def _ensure_llm(self):
        if not self._llm:
            from backend.app.services.llm.client import get_llm
            self._llm = await get_llm(temperature=0.0)
            self._structured_llm = self._llm.with_structured_output(VerificationOutcome, strict=True)

    async def verify_candidate(self, candidate: Dict[str, Any], execution_trace: List[str]) -> VerificationOutcome:
        """
        Validates if a semantic memory candidate is directly grounded in the raw conversation/trace.
        """
        await self._ensure_llm()
        entity = candidate.get("entity", "unknown")
        fact = candidate.get("fact", "")
        stated_confidence = candidate.get("confidence_score", 0.0)
        
        trace_block = "\n".join(execution_trace[-15:])  # Last 15 messages for context
        
        verification_prompt = f"""You are an anti-hallucination auditor. Your task is to verify whether a candidate semantic memory is **directly supported** by the raw execution trace below.

[CANDIDATE MEMORY]
Entity: {entity}
Fact: {fact}
Stated Confidence: {stated_confidence}

[RAW EXECUTION TRACE]
{trace_block}

RULES:
1. The fact MUST be explicitly stated or directly inferable from the trace. Do NOT accept vague implications.
2. If the fact contains quantitative claims, the exact numbers must appear in the trace.
3. If the fact is about user preferences, the user must have explicitly expressed it.
4. Adjust the confidence_adjustment score: 
   - 0.9-1.0: Fact is explicitly and unambiguously stated in trace
   - 0.7-0.89: Fact is strongly implied by multiple trace entries
   - 0.5-0.69: Fact has partial support but requires inference
   - Below 0.5: Reject (set verified=false)
5. Provide a concise justification pointing to specific trace entries.
"""
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a strict factual grounding verifier. You validate memories against execution evidence."),
            ("human", "{verification_prompt}")
        ])
        
        try:
            chain = prompt_template | self._structured_llm
            result = await chain.ainvoke({"verification_prompt": verification_prompt})
            
            logger.debug(
                f"[MemoryVerifier] Entity='{entity}' | Verified={result.verified} | "
                f"AdjustedConf={result.confidence_adjustment:.2f} | Justification={result.justification[:100]}"
            )
            return result
            
        except Exception as e:
            logger.error(f"[MemoryVerifier] Grounding verification failed for entity='{entity}': {e}")
            # On failure, reject the candidate to be safe
            return VerificationOutcome(
                verified=False,
                confidence_adjustment=0.0,
                justification=f"Verification system error: {str(e)[:200]}"
            )
