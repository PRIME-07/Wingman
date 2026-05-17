import os
import yaml
from typing import Dict, Any, Optional
from backend.app.core.logging import logger

# Built-in Fallback prompts to ensure operational continuity
DEFAULT_FALLBACKS = {
    "orchestrator_system": """You are Wingman, an elite AI Assistant Operating System.
Your objective is to dynamically execute the requested goal using your tool suite.
Maintain a crisp, professional, yet personalized demeanor.
You MUST express your reaction at the beginning of EVERY response by outputting: [EXPRESSION: <tag>]
Allowed tags: [angry, bored, confused, embarrassed, excited, glad, happy, inLove, laughing, neutral, proud, recollecting, sad, shocked, shy, skeptical, sleepy, thankful, thinking, worried]""",
    
    "planner_instruction": """You are an elite AI Systems Architect. 
Your objective is to break down the user's goal into sequential plan steps.""",
    
    "reflection_critique": """You are the Cognitive Reflection Layer.
Evaluate execution outcomes and distill insights for storage.""",
    
    "working_memory_summarize": """Synthesize and merge the previous summary with the current dialog chunk cleanly."""
}

class PromptRegistry:
    """
    Dynamic loader and cacher for versioned text and chat prompts.
    Prevents hardcoding and supports semantic version tagging for evaluation metrics.
    """
    def __init__(self):
        self._prompts_dir = os.path.join(os.path.dirname(__file__), "templates")
        self._cache: Dict[str, Dict[str, str]] = {} # Outer: prompt_id, Inner: version_tag -> content

    def get_prompt(self, prompt_id: str, version: str = "latest") -> str:
        """
        Fetches specified prompt string. Caches files on first load.
        Returns fallback if directory/file does not exist.
        """
        # 1. Try Memory Cache
        if prompt_id in self._cache and version in self._cache[prompt_id]:
            return self._cache[prompt_id][version]
            
        # 2. Attempt disk resolution
        file_path = os.path.join(self._prompts_dir, f"{prompt_id}.yaml")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    
                versions = data.get("versions", {})
                active_version = data.get("active_version", "v1.0.0")
                
                target_version = active_version if version == "latest" else version
                
                prompt_content = versions.get(target_version)
                if prompt_content:
                    if prompt_id not in self._cache:
                        self._cache[prompt_id] = {}
                    self._cache[prompt_id][target_version] = prompt_content
                    logger.debug(f"[Prompts] Loaded dynamic prompt '{prompt_id}' [ver={target_version}]")
                    return prompt_content
                    
                logger.warning(f"[Prompts] Version '{version}' not found for {prompt_id}. Falling back.")
            except Exception as e:
                logger.error(f"[Prompts] Error loading dynamic prompt file {prompt_id}: {e}")
                
        # 3. Graceful Default Fallback
        logger.debug(f"[Prompts] Serving hardcoded default fallback for '{prompt_id}'")
        return DEFAULT_FALLBACKS.get(prompt_id, "You are a helpful assistant.")

# Central provider instance
prompt_registry = PromptRegistry()
