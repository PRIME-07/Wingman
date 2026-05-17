import aiohttp
from typing import Any, Dict, Optional
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.services.credentials.manager import credential_manager

class WeatherService:
    """
    Queries meteorological endpoints via aiohttp to provide high-fidelity 
    local forecast summaries, current temperatures, and severe storm metrics.
    """

    def __init__(self):
        # Using robust WeatherAPI.com standard endpoint mappings
        self.base_url = "http://api.weatherapi.com/v1"

    async def get_forecast(self, location: str, days: int = 3) -> Dict[str, Any]:
        """
        Fetches contemporary conditions and future prognoses for specified cities or coordinates.
        Gracefully yields simulated payloads if API key is unassigned for seamless testing.
        """
        api_key = await credential_manager.get_secret("weather_api_key", provider="tools")
        if not api_key or "your-openweathermap" in api_key or len(api_key) < 10:
            logger.warning("[WeatherService] Missing active WEATHER_API_KEY. Running mock generator.")
            return self._get_mock_response(location)

        # OpenWeatherMap integration
        base_url = "https://api.openweathermap.org/data/2.5"
        weather_endpoint = f"{base_url}/weather"
        forecast_endpoint = f"{base_url}/forecast"
        
        params = {
            "appid": api_key,
            "units": "imperial"
        }
        
        # Intelligently parse numeric coordinate overrides
        coords_detected = False
        if "," in location:
            try:
                parts = [p.strip() for p in location.split(",")]
                if len(parts) == 2:
                    params["lat"] = float(parts[0])
                    params["lon"] = float(parts[1])
                    coords_detected = True
            except ValueError:
                pass
                
        if not coords_detected:
            params["q"] = location

        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"[WeatherService] Dispatching OpenWeatherMap evaluation for location='{location}'...")
                
                # Fetch current weather
                async with session.get(weather_endpoint, params=params) as resp_current:
                    if resp_current.status != 200:
                        raw_err = await resp_current.text()
                        logger.warning(f"[WeatherService] API rejected current query status={resp_current.status}: {raw_err}. Dropping into simulation...")
                        return self._get_mock_response(location)
                    current_data = await resp_current.json()
                
                # Fetch forecast
                async with session.get(forecast_endpoint, params=params) as resp_forecast:
                    forecast_data = await resp_forecast.json() if resp_forecast.status == 200 else {}
                
                # Map OpenWeatherMap to the structure expected by tool.py (which was designed for weatherapi.com)
                mapped_data = {
                    "location": {
                        "name": current_data.get("name"),
                        "region": current_data.get("sys", {}).get("country"),
                        "localtime": "Local time (OWM)"
                    },
                    "current": {
                        "temp_f": current_data.get("main", {}).get("temp"),
                        "temp_c": (current_data.get("main", {}).get("temp", 32) - 32) * 5.0/9.0,
                        "feelslike_f": current_data.get("main", {}).get("feels_like"),
                        "humidity": current_data.get("main", {}).get("humidity"),
                        "wind_mph": current_data.get("wind", {}).get("speed"),
                        "condition": {
                            "text": current_data.get("weather", [{}])[0].get("description", "").title()
                        }
                    },
                    "forecast": {
                        "forecastday": []
                    }
                }
                
                # Try to map 3-hour forecasts to daily if available
                if forecast_data and "list" in forecast_data:
                    # Very simple grouping by date
                    days_seen = set()
                    for item in forecast_data["list"]:
                        date_str = item.get("dt_txt", "").split(" ")[0]
                        if date_str and date_str not in days_seen and len(days_seen) < days:
                            days_seen.add(date_str)
                            mapped_data["forecast"]["forecastday"].append({
                                "date": date_str,
                                "day": {
                                    "maxtemp_f": item.get("main", {}).get("temp_max"),
                                    "mintemp_f": item.get("main", {}).get("temp_min"),
                                    "daily_chance_of_rain": int(item.get("pop", 0) * 100),
                                    "condition": {
                                        "text": item.get("weather", [{}])[0].get("description", "").title()
                                    }
                                }
                            })
                            
                return {"success": True, "data": mapped_data}
        except Exception as e:
            logger.warning(f"[WeatherService] Network connection aborted ({e}). Restoring fallback output.")
            return self._get_mock_response(location)

    def _get_mock_response(self, location: str) -> Dict[str, Any]:
        """Consistently returns simulated high fidelity weather payload."""
        return {
            "simulated": True,
            "location": location,
            "current": {
                "temp_c": 21.0, "temp_f": 69.8, 
                "condition": "Partly Cloudy (Simulated)", 
                "humidity": 45
            },
            "forecast": [
                {"date": "Today", "max_temp_f": 72.5, "min_temp_f": 55.2, "condition": "Sunny"},
                {"date": "Tomorrow", "max_temp_f": 68.0, "min_temp_f": 52.4, "condition": "Patchy rain"},
            ]
        }


# Singleton wrapper
weather_service = WeatherService()
