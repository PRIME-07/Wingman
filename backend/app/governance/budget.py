import threading
from typing import Dict, Tuple
from backend.app.core.logging import logger

class InferenceBudgetManager:
    """
    Priority 9 Governance: Monitors cumulative token consumption per session 
    and enforces adaptive reasoning-effort degradation to prevent token spikes.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, session_hard_limit: int = 150000, session_soft_limit: int = 80000):
        if self._initialized:
            return
            
        # In-memory local store. Production systems should scale to Redis Hash.
        # Key = Session ID, Value = (cumulative_tokens)
        self._registry: Dict[str, int] = {}
        self._hard_limit = session_hard_limit
        self._soft_limit = session_soft_limit
        self._initialized = True
        logger.info(f"[BudgetManager] Initialized limits: Soft={self._soft_limit} | Hard={self._hard_limit}")

    def record_tokens(self, session_id: str, token_count: int):
        """Accumulates consumed tokens into the running session register."""
        if not session_id or session_id == "unknown":
            return
            
        with self._lock:
            current = self._registry.get(session_id, 0)
            new_total = current + token_count
            self._registry[session_id] = new_total
            
            if new_total > self._hard_limit:
                logger.warning(
                    f"[BudgetManager] CRITICAL EXCEEDED HARD LIMIT for Session={session_id}: "
                    f"{new_total}/{self._hard_limit} tokens"
                )
            elif new_total > self._soft_limit:
                logger.warning(
                    f"[BudgetManager] Warning: Soft limit exceeded for Session={session_id}: "
                    f"{new_total}/{self._soft_limit} tokens. Recommending degraded effort."
                )

    def get_enforced_effort(self, session_id: str, requested_effort: str) -> Tuple[str, str]:
        """
        Audits the session cost and returns downgraded reasoning tiers if limits are broken.
        Returns (applied_effort, advice_message)
        """
        if not session_id or session_id == "unknown":
            return requested_effort, "untracked"

        with self._lock:
            total = self._registry.get(session_id, 0)

        # Degrade logic
        if total > self._hard_limit:
            # Force extreme cost containment
            return "low", "forced_degrade_hard"
        elif total > self._soft_limit:
            # Step down high -> medium
            if requested_effort == "high":
                return "medium", "forced_degrade_soft"
        
        return requested_effort, "allowed"

    def get_session_usage(self, session_id: str) -> int:
        with self._lock:
            return self._registry.get(session_id, 0)

    def reset_session(self, session_id: str):
        with self._lock:
            self._registry.pop(session_id, None)

# Singleton Access
budget_manager = InferenceBudgetManager()
