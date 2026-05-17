from datetime import datetime, time, timedelta
from typing import Dict
from backend.app.quota.models import ProviderQuota
from backend.app.memory.mongodb_client import mongo_client
from backend.app.core.logging import logger

DEFAULT_QUOTAS = {
    "google": 100,
    "youtube": 50,
    "slack": 500,
    "weather": 50,
    "maps": 100,
}

class QuotaGovernanceEngine:
    """
    Maintains precise real-time usage limits on third-party service endpoints, 
    offering dynamic rate-limiting to feed the capability matrix.
    """
    
    def _get_reset_time(self) -> datetime:
        """Calculates the next midnight rollover timestamp."""
        now = datetime.utcnow()
        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, time.min)

    async def get_quota(self, provider: str) -> ProviderQuota:
        """Fetches active quota object, performing automated daily resets if needed."""
        try:
            mongo_client.connect()
            coll = mongo_client.db["api_quotas"]
            
            doc = await coll.find_one({"provider": provider})
            now = datetime.utcnow()
            
            if doc:
                quota = ProviderQuota.model_validate(doc)
                # Check for daily rollover reset condition
                if now >= quota.reset_at:
                    quota.current_count = 0
                    quota.reset_at = self._get_reset_time()
                    await coll.replace_one({"provider": provider}, quota.model_dump())
                    logger.info(f"[QuotaEngine] Rolled over daily quota limit for provider='{provider}'.")
                return quota
                
            # Provision fresh initial quota
            limit = DEFAULT_QUOTAS.get(provider, 1000)
            new_quota = ProviderQuota(
                provider=provider,
                daily_limit=limit,
                reset_at=self._get_reset_time()
            )
            await coll.insert_one(new_quota.model_dump())
            return new_quota
            
        except Exception as e:
            logger.error(f"[QuotaEngine] Quota fetch error for '{provider}': {e}")
            # Return safe unblocked fallback to prevent cascading system crash
            return ProviderQuota(provider=provider, daily_limit=9999, current_count=0)

    async def check_quota(self, provider: str) -> bool:
        """Returns True if execution operations are permitted for this provider."""
        quota = await self.get_quota(provider)
        return quota.ok

    async def record_usage(self, provider: str, count: int = 1) -> bool:
        """Increments usage counters inside MongoDB transactional increments."""
        try:
            # Make sure the quota model is initialized first
            await self.get_quota(provider)
            
            mongo_client.connect()
            coll = mongo_client.db["api_quotas"]
            
            await coll.update_one(
                {"provider": provider},
                {"$inc": {"current_count": count}}
            )
            return True
        except Exception as e:
            logger.error(f"[QuotaEngine] Failed to increment usage for '{provider}': {e}")
            return False

# Singleton instance
quota_governance = QuotaGovernanceEngine()
