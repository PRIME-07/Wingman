import httpx
from typing import Dict, Any, Optional
from backend.app.core.logging import logger

class CredentialValidator:
    @staticmethod
    async def validate_openai(api_key: str) -> bool:
        if not api_key: return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"OpenAI validation failed: {e}")
            return False

    @staticmethod
    async def validate_tavily(api_key: str) -> bool:
        if not api_key: return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={"query": "test", "api_key": api_key},
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Tavily validation failed: {e}")
            return False

    @staticmethod
    async def validate_weather(api_key: str) -> bool:
        if not api_key: return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.openweathermap.org/data/2.5/weather?q=London&appid={api_key}",
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Weather validation failed: {e}")
            return False

    @staticmethod
    async def validate_google_maps(api_key: str) -> bool:
        if not api_key: return False
        try:
            async with httpx.AsyncClient() as client:
                # User requested Places (New) API validation. 
                # This is more robust as many "Maps" keys have Places enabled but not Geocoding.
                response = await client.post(
                    "https://places.googleapis.com/v1/places:searchText",
                    headers={
                        "X-Goog-Api-Key": api_key,
                        "X-Goog-FieldMask": "places.displayName",
                        "Content-Type": "application/json"
                    },
                    json={"textQuery": "Googleplex"},
                    timeout=10.0
                )
                # status_code 200 means the key is valid and the API is enabled.
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Google Maps validation failed: {e}")
            return False

    @staticmethod
    async def validate_youtube(api_key: str) -> bool:
        if not api_key: return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://www.googleapis.com/youtube/v3/videos?id=7lCDEYXw3mM&key={api_key}&part=snippet",
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"YouTube validation failed: {e}")
            return False

    @staticmethod
    async def validate_slack(token: str) -> bool:
        if not token: return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )
                data = response.json()
                return data.get("ok", False)
        except Exception as e:
            logger.error(f"Slack validation failed: {e}")
            return False


    @staticmethod
    async def validate_google_oauth(client_id: str, client_secret: str) -> bool:
        if not client_id or not client_secret: return False
        # Format check
        if not client_id.endswith(".apps.googleusercontent.com"):
            return False
        if not client_secret.startswith("GOCSPX-") and len(client_secret) < 20:
             return False
        
        try:
            # Check if discovery doc is reachable
            async with httpx.AsyncClient() as client:
                response = await client.get("https://accounts.google.com/.well-known/openid-configuration")
                return response.status_code == 200
        except Exception:
            return False

validator = CredentialValidator()
