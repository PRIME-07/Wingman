from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any, Literal

from enum import Enum

class MemoryCategory(str, Enum):
    FACT = "Fact"               # Fully verified, objective statements
    PREFERENCE = "Preference"   # Direct user style, workflow, or lifestyle choices
    ASSUMPTION = "Assumption"   # Speculative LLM-inferred details (Temporary)
    HYPOTHESIS = "Hypothesis"   # Testing causal links (Requires confirmation)
    CONTEXT = "Context"         # Temporal details bound to a single project or event

class CognitiveMemoryCandidate(BaseModel):
    """Represents a single distilled insight recommended for permanent semantic graph storage."""
    model_config = ConfigDict(extra="forbid")
    
    entity: str = Field(description="Core node subject, e.g. 'user', 'project-X', 'Python'")
    fact: str = Field(description="Granular statement about the entity to commit to memory.")
    importance_score: float = Field(description="Mandatory importance level (0.0 - 1.0).")
    confidence_score: float = Field(description="Confidence in accuracy / truth probability (0.0 - 1.0).")
    category: Literal["Fact", "Preference", "Assumption", "Hypothesis", "Context"] = Field(
        description="Strict epistemological classification. Must be one of: Fact, Preference, Assumption, Hypothesis, Context."
    )

class ReflectionOutcome(BaseModel):
    """Result of the post-execution self-critique and cognitive synthesis cycle."""
    model_config = ConfigDict(extra="forbid")
    
    goal_achieved: bool = Field(description="Did the system satisfy the user's original goal requirements?")
    assessment: str = Field(description="Natural language evaluation of system performance.")
    reasoning_gaps: str = Field(description="Shortcomings or mistakes identified during execution. Use empty string if none.")
    score: int = Field(description="Self-assigned quality rating from 1-10.")
    suggested_memories: List[CognitiveMemoryCandidate] = Field(
        description="List of facts or lessons extracted for storage consideration. Use empty list if none."
    )
    next_steps: str = Field(description="Recommended corrective actions if goal_achieved is False. Use empty string if none.")
