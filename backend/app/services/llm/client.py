from typing import Optional, Any, Dict
from langchain_openai import ChatOpenAI
from backend.app.core.config import settings
from backend.app.core.logging import logger

async def get_llm(
    model_name: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    streaming: bool = True,
    session_id: Optional[str] = None,
    **kwargs: Any
) -> ChatOpenAI:
    """
    Centralized factory for constructing standard OpenAI LLM instances.
    Injects dynamic model name, reasoning_effort configurations and overrides automatically.
    Integrates P9 Budget Enforcement to downgrade reasoning levels under cost spikes.
    """
    # Prioritize dynamic model override, normalize to lowercase for API reliability
    resolved_model = model_name.lower() if model_name is not None else settings.OPENAI_MODEL
    
    model_name = resolved_model
    
    # Resolve params prioritizing invocation arguments then config settings
    llm_temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    llm_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
    llm_effort = reasoning_effort if reasoning_effort is not None else settings.REASONING_EFFORT

    # P9 Enforced Cost Governance
    if session_id:
        from backend.app.governance.budget import budget_manager
        original_effort = llm_effort
        llm_effort, advice = budget_manager.get_enforced_effort(session_id, llm_effort)
        
        if llm_effort != original_effort:
            logger.warning(
                f"[BudgetEnforcer] Dynamically downgraded reasoning_effort for Session={session_id} "
                f"from '{original_effort}' to '{llm_effort}' due to budget rule: {advice}"
            )

    # Resolve API Key dynamically from Secure Storage
    from backend.app.services.credentials.manager import credential_manager
    api_key = await credential_manager.get_secret("openai_api_key", provider="engine")

    # Prepare model constructor args
    client_args: Dict[str, Any] = {
        "model": model_name,
        "openai_api_key": api_key,
        "streaming": streaming,
        "temperature": llm_temp,
        "max_tokens": llm_tokens,
        **kwargs
    }
    
    # Reasoning effort is only supported by o1, o3, and the user-specified gpt-5.4-mini
    is_reasoning_model = any(model_name.startswith(p) for p in ["o1", "o3", "gpt-5.4"])
    
    # Route to /v1/responses only for models that support/require it (like o1/o3/gpt-5.4)
    # Standard models like gpt-4o-mini use the traditional Chat Completions API.
    client_args["use_responses_api"] = is_reasoning_model
    
    if is_reasoning_model and llm_effort in ["low", "medium", "high"]:
        # Use explicit parameter for modern langchain-openai compatibility
        client_args["reasoning_effort"] = llm_effort
    elif llm_effort in ["low", "medium", "high"]:
        # For non-reasoning models, we should not pass the parameter at all
        logger.debug(f"Skipping reasoning_effort for non-reasoning model: {model_name}")
        
    logger.info(
        f"Initializing LLM layer: Model={model_name}, "
        f"ReasoningEffort={llm_effort}, Temperature={llm_temp}, Streaming={streaming}"
    )
    
    try:
        return ChatOpenAI(**client_args)
    except Exception as e:
        logger.error(f"Failed to instantiate LLM client: {e}")
        raise
