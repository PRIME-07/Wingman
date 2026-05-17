import aiohttp
from typing import Any, Dict, List, Optional
from backend.app.core.config import settings
from backend.app.core.logging import logger

class YoutubeService:
    """
    Interfaces with Google YouTube Data API v3 asynchronously via aiohttp.
    Provides discovery search queries to link relevant video IDs, channels, 
    and descriptions back to the Wingman orchestrator.
    """

    def __init__(self):
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def search_videos(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Searches YouTube for active public video contents matching the input query.
        Yields curated mock outputs if configuration keys are absent.
        """
        from backend.app.services.credentials.manager import credential_manager
        api_key = await credential_manager.get_secret("youtube_api_key", provider="tools")
        if not api_key or "your-google-api-youtube-key" in api_key:
            logger.warning("[YoutubeService] YouTube configuration key is absent. Emitting simulations.")
            return {
                "simulated": True,
                "items": [
                    {
                        "id": {"videoId": "dQw4w9WgXcQ"},
                        "snippet": {
                            "title": "Never Gonna Give You Up (Simulated)",
                            "description": "Official simulated performance testing payload.",
                            "channelTitle": "Rick Astley",
                            "publishedAt": "2009-10-25T00:00:00Z"
                        }
                    },
                    {
                        "id": {"videoId": "mcdonal"},
                        "snippet": {
                            "title": "AI Agents in 2026 - The Future (Simulated)",
                            "description": "Exploring robust autonomous agents.",
                            "channelTitle": "Tech Insider",
                            "publishedAt": "2026-01-12T09:30:00Z"
                        }
                    }
                ]
            }

        endpoint = f"{self.base_url}/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "key": api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"[YoutubeService] Querying YouTube API for keyphrase='{query}'...")
                async with session.get(endpoint, params=params) as resp:
                    if resp.status != 200:
                        raw_err = await resp.text()
                        logger.warning(f"[YoutubeService] Remote API failure status={resp.status}: {raw_err}. Cascading to simulation.")
                        return self._get_mock_response()
                        
                    result = await resp.json()
                    return {"success": True, "data": result}
        except Exception as e:
            logger.warning(f"[YoutubeService] Failed connection to search cluster: {e}. Emitting simulation.")
            return self._get_mock_response()

    def _get_mock_response(self) -> Dict[str, Any]:
        """Consistently delivers structured mock Youtube payloads."""
        return {
            "simulated": True,
            "items": [
                {
                    "id": {"videoId": "dQw4w9WgXcQ"},
                    "snippet": {
                        "title": "Never Gonna Give You Up (Simulated)",
                        "description": "Official simulated performance testing payload.",
                        "channelTitle": "Rick Astley",
                        "publishedAt": "2009-10-25T00:00:00Z"
                    }
                },
                {
                    "id": {"videoId": "mcdonal"},
                    "snippet": {
                        "title": "AI Agents in 2026 - The Future (Simulated)",
                        "description": "Exploring robust autonomous agents.",
                        "channelTitle": "Tech Insider",
                        "publishedAt": "2026-01-12T09:30:00Z"
                    }
                }
            ]
        }


# Singleton registry
youtube_service = YoutubeService()
