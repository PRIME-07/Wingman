import aiohttp
from typing import Any, Dict, Optional
from backend.app.core.config import settings
from backend.app.core.logging import logger

class GoogleMapsService:
    """
    Leverages asynchronous network queries via aiohttp to evaluate traffic patterns,
    ETA calculations, and granular navigation routings using Google Directions APIs.
    """

    def __init__(self):
        self.base_url = "https://maps.googleapis.com/maps/api"

    async def get_directions(
        self, 
        origin: str, 
        destination: str, 
        mode: str = "driving",
        traffic_model: str = "best_guess",
        departure_time: str = "now"
    ) -> Dict[str, Any]:
        """
        Queries the Google Directions API to compute optimized routing pathways.
        Extracts distances, duration estimates (accounting for active traffic), and overview layouts.
        """
        from backend.app.services.credentials.manager import credential_manager
        api_key = await credential_manager.get_secret("google_maps_api_key", provider="tools")
        if not api_key or "your-google-maps-api-key" in api_key:
            logger.warning("[MapsService] Missing or placeholder GOOGLE_MAPS_API_KEY. Falling back to simulation.")
            # Safe local simulator when key is unconfigured
            return {
                "simulated": True,
                "status": "OK",
                "routes": [{
                    "summary": "I-95 S (Simulated)",
                    "legs": [{
                        "distance": {"text": "12.4 miles", "value": 19955},
                        "duration": {"text": "22 mins", "value": 1320},
                        "duration_in_traffic": {"text": "27 mins", "value": 1620},
                        "start_address": origin,
                        "end_address": destination
                    }]
                }]
            }

        params = {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "key": api_key
        }
        
        # Traffic features require specific modes and timestamps
        if mode == "driving" and departure_time == "now":
            params["departure_time"] = "now"
            params["traffic_model"] = traffic_model

        endpoint = f"{self.base_url}/directions/json"
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"[MapsService] Dispatching Directions request from='{origin}' to='{destination}'.")
                async with session.get(endpoint, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"[MapsService] Maps API returned status={resp.status}")
                        raise RuntimeError(f"Google Maps API unavailable ({resp.status})")
                        
                    result = await resp.json()
                    
                    if result.get("status") != "OK":
                        err_msg = result.get("error_message", "Unknown API Error")
                        logger.error(f"[MapsService] Directions query returned error: {result.get('status')} - {err_msg}")
                        return {"success": False, "status": result.get("status"), "message": err_msg}
                        
                    return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"[MapsService] Asynchronous network error: {e}", exc_info=True)
            raise

    async def get_nearby_places(
        self,
        query: str,
        location: str,
        radius_meters: int = 5000
    ) -> Dict[str, Any]:
        """
        Leverages the Google Places API (Nearby Search) to locate entities (shops, coffee, parks)
        within a specified boundary radius of the user's current spatial location.
        """
        from backend.app.services.credentials.manager import credential_manager
        api_key = await credential_manager.get_secret("google_maps_api_key", provider="tools")
        if not api_key or "your-google-maps-api-key" in api_key:
            logger.warning("[MapsService] Missing or placeholder GOOGLE_MAPS_API_KEY. Simulating Places results.")
            return {
                "simulated": True,
                "status": "OK",
                "results": [
                    {
                        "name": f"Simulated Café near {query}",
                        "vicinity": f"123 Mockingbird Ln, coordinates context: {location}",
                        "rating": 4.8,
                        "user_ratings_total": 142,
                        "geometry": {"location": {"lat": 37.7749, "lng": -122.4194}}
                    },
                    {
                        "name": f"Hypothetical {query.title()} Store",
                        "vicinity": "456 Placeholder Pkwy",
                        "rating": 4.3,
                        "user_ratings_total": 89,
                        "geometry": {"location": {"lat": 37.7833, "lng": -122.4167}}
                    }
                ]
            }

        params = {
            "location": location,
            "radius": str(radius_meters),
            "keyword": query,
            "key": api_key
        }

        endpoint = f"{self.base_url}/place/nearbysearch/json"

        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"[MapsService] Dispatching Nearby Search for '{query}' around '{location}' radius={radius_meters}m.")
                async with session.get(endpoint, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"[MapsService] Places API returned status={resp.status}")
                        raise RuntimeError(f"Google Places API unavailable ({resp.status})")
                        
                    result = await resp.json()
                    
                    if result.get("status") not in ("OK", "ZERO_RESULTS"):
                        err_msg = result.get("error_message", "Unknown API Error")
                        logger.error(f"[MapsService] Places query returned error: {result.get('status')} - {err_msg}")
                        return {"success": False, "status": result.get("status"), "message": err_msg}
                        
                    return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"[MapsService] Asynchronous network error during Places search: {e}", exc_info=True)
            raise

# Singleton instance
google_maps_service = GoogleMapsService()
