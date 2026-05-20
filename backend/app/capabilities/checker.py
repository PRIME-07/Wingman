from typing import Dict
import aiohttp
from backend.app.capabilities.models import ToolCapability
from backend.app.services.credentials.manager import credential_manager
from backend.app.core.config import settings
from backend.app.core.logging import logger

class CapabilityDiscoveryEngine:
    """
    Executes live queries against runtime credentials and endpoints to verify 
    whether tools can perform live transactions or must be bypassed.
    """

    async def discover_capabilities(self) -> Dict[str, ToolCapability]:
        """Inspects key system providers to form the complete Capability Matrix."""
        from backend.app.quota.governance import quota_governance
        capabilities = {}
        
        # 1. Clock & Simple Local Utilities (Always True)
        always_ok = ToolCapability(available=True, authenticated=True, quota_ok=True, provider_reachable=True)
        capabilities["clock"] = always_ok
        capabilities["timer_set"] = always_ok
        capabilities["timer_cancel"] = always_ok
        capabilities["timer_list"] = always_ok
        capabilities["memory_retrieval"] = always_ok

        # Fetch live quotas
        slack_q = await quota_governance.get_quota("slack")
        weather_q = await quota_governance.get_quota("weather")
        google_q = await quota_governance.get_quota("google")
        maps_q = await quota_governance.get_quota("maps")
        youtube_q = await quota_governance.get_quota("youtube")

        # 2. Slack Capability
        slack_cap = await self._check_slack()
        if not slack_q.ok:
            slack_cap.quota_ok = False
            slack_cap.available = False
            slack_cap.reason = f"Daily Quota Exceeded ({slack_q.current_count}/{slack_q.daily_limit})"
        capabilities["slack_message"] = slack_cap
        capabilities["slack_channel_list"] = slack_cap

        # 3. Weather API Capability
        weather_cap = await self._check_weather()
        if not weather_q.ok:
            weather_cap.quota_ok = False
            weather_cap.available = False
            weather_cap.reason = f"Daily Quota Exceeded ({weather_q.current_count}/{weather_q.daily_limit})"
        capabilities["weather_query"] = weather_cap

        # 4. Google Suite Capability (Gmail, Docs, Calendar, Maps)
        google_cap = await self._check_google()
        if not google_q.ok:
            google_cap.available = False
            google_cap.reason = f"Daily Quota Exceeded ({google_q.current_count}/{google_q.daily_limit})"
        capabilities["gmail_draft"] = google_cap
        capabilities["calendar_schedule"] = google_cap
        capabilities["calendar_modify"] = google_cap
        capabilities["calendar_delete"] = google_cap
        capabilities["calendar_batch_schedule"] = google_cap
        capabilities["calendar_batch_modify"] = google_cap
        capabilities["calendar_batch_delete"] = google_cap
        capabilities["calendar_query"] = google_cap
        capabilities["docs_create"] = google_cap
        capabilities["docs_read"] = google_cap
        capabilities["docs_edit"] = google_cap
        capabilities["docs_search"] = google_cap
        
        # 5. Google Maps & YouTube (Uses API keys)
        maps_cap = await self._check_public_google_api("maps")
        if not maps_q.ok:
            maps_cap.available = False
            maps_cap.reason = f"Daily Quota Exceeded ({maps_q.current_count}/{maps_q.daily_limit})"
        capabilities["maps_directions"] = maps_cap
        capabilities["google_maps_directions"] = maps_cap
        capabilities["google_maps_nearby_search"] = maps_cap
        
        youtube_cap = await self._check_public_google_api("youtube")
        if not youtube_q.ok:
            youtube_cap.available = False
            youtube_cap.reason = f"Daily Quota Exceeded ({youtube_q.current_count}/{youtube_q.daily_limit})"
        capabilities["youtube_search"] = youtube_cap
        
        # 6. Web Search
        capabilities["web_search"] = always_ok # Simple mock fallback is always fine

        return capabilities


    async def _check_slack(self) -> ToolCapability:
        """Assesses Slack authorization status."""
        try:
            creds = await credential_manager.get_credential("slack")
            bot_token = await credential_manager.get_secret("slack_bot_token", provider="slack")
            
            if not creds and not bot_token:
                return ToolCapability(available=False, authenticated=False, reason="Missing SLACK_BOT_TOKEN")
            return ToolCapability(available=True, authenticated=True, provider_reachable=True)
        except Exception as e:
            logger.error(f"[Cap-Discovery] Slack check failed: {e}")
            return ToolCapability(available=False, authenticated=False, reason=str(e))

    async def _check_weather(self) -> ToolCapability:
        """Checks OpenWeatherMap token and uptime."""
        api_key = await credential_manager.get_secret("weather_api_key", provider="tools")
        if not api_key or len(api_key) < 10:
            return ToolCapability(available=False, authenticated=False, reason="No Weather API key provided")
            
        # Try immediate lightweight ping using OpenWeatherMap (London query)
        try:
            params = {"appid": api_key, "q": "London"}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                async with session.get("https://api.openweathermap.org/data/2.5/weather", params=params) as resp:
                    if resp.status == 403 or resp.status == 401:
                        return ToolCapability(available=False, authenticated=False, reason="Invalid Weather API key")
                    return ToolCapability(available=True, authenticated=True, provider_reachable=resp.status < 500)
        except Exception as e:
            logger.warning(f"[Cap-Discovery] Weather ping failed: {e}")
            return ToolCapability(available=True, provider_reachable=False, reason="Weather network unreachable")

    async def _check_google(self) -> ToolCapability:
        """Checks centralized OAuth states for Google Suite services."""
        try:
            token = await credential_manager.get_credential("google")
            if not token:
                 return ToolCapability(available=False, authenticated=False, reason="Google OAuth token missing. Connect account first.")
            return ToolCapability(available=True, authenticated=True)
        except Exception:
            return ToolCapability(available=False, authenticated=False, reason="Google storage failure")

    async def _check_public_google_api(self, service: str) -> ToolCapability:
        """Checks availability of public API key-based endpoints."""
        key_name = "youtube_api_key" if service == "youtube" else "google_maps_api_key"
        key = await credential_manager.get_secret(key_name, provider="tools")
        
        if not key or "AIza" not in key:
            return ToolCapability(available=False, authenticated=False, reason=f"Missing public Google {service} token")
        return ToolCapability(available=True, authenticated=True)

# Centralized engine pointer
capability_discovery = CapabilityDiscoveryEngine()
