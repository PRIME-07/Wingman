from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext
from backend.app.core.logging import logger
from backend.app.services.weather.service import weather_service

class WeatherQueryInput(BaseModel):
    location: str = Field(..., description="Target city name, zip code, or coordinates.")
    days: int = Field(3, description="Number of forecast days requested (max 7).")

class WeatherQueryTool(BaseWingmanTool):
    """
    Queries global weather networks.
    Extracts temperature values, severe weather indices, precipitation forecasts, and relative humidity.
    """
    name = "weather_query"
    description = "Fetches current local weather reports and multi-day forecasts."
    args_schema = WeatherQueryInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        loc = args["location"]
        days = min(max(args.get("days", 3), 1), 7)
        
        # Dynamic Spatial Resolve Interceptor
        implicit_keywords = {"here", "current", "me", "my location", "local", "now", "."}
        user_loc = context.metadata.get("location") if context.metadata else None
        
        if (not loc or loc.lower().strip() in implicit_keywords) and user_loc:
            lat = user_loc.get("latitude")
            lon = user_loc.get("longitude")
            if lat is not None and lon is not None:
                loc = f"{lat},{lon}"
                logger.info(f"[WeatherTool] Injected explicit spatial context coordinates: {loc}")
                # Emit spatial telemetry event using standard helper (imported inside subagent context)
                from backend.app.graphs.execution.helpers import emit_telemetry
                from backend.app.telemetry.schemas import TelemetryEventType
                
                # Reconstruct dynamic state mapping for helper delivery
                telemetry_state = {
                    "trace_id": context.trace_id,
                    "run_id": context.run_id,
                    "session_id": "active-session" # fallback identifier
                }
                
                await emit_telemetry(
                    telemetry_state,
                    TelemetryEventType.SPATIAL_RESOLVED,
                    tool_name=self.name,
                    payload={
                        "original_query": args["location"],
                        "resolved_coordinates": f"{lat:.4f}, {lon:.4f}",
                        "provider": "browser_geolocation"
                    }
                )

        logger.info(f"[WeatherTool] Querying atmospheric state for: '{loc}' for {days} days.")
        
        try:
            res = await weather_service.get_forecast(loc, days)
            
            if res.get("simulated", False):
                return {
                    "success": True,
                    "is_simulation": True,
                    "location": res["location"],
                    "current": res["current"],
                    "forecast": res["forecast"],
                    "notice": "Generated simulated forecast. Provide API key to load real updates."
                }
                
            # Restructure real payload into ultra-tight telemetry-ready model
            data = res["data"]
            current = data.get("current", {})
            location_meta = data.get("location", {})
            forecast_days = data.get("forecast", {}).get("forecastday", [])
            
            condensed_forecast = []
            for day in forecast_days:
                day_info = day.get("day", {})
                condensed_forecast.append({
                    "date": day.get("date"),
                    "max_temp_f": day_info.get("maxtemp_f"),
                    "min_temp_f": day_info.get("mintemp_f"),
                    "rain_chance": day_info.get("daily_chance_of_rain"),
                    "condition": day_info.get("condition", {}).get("text")
                })

            logger.info(f"[WeatherTool] Forecast successfully compiled for '{location_meta.get('name')}'.")
            
            return {
                "success": True,
                "location": f"{location_meta.get('name')}, {location_meta.get('region')}",
                "localtime": location_meta.get("localtime"),
                "current": {
                    "temp_f": current.get("temp_f"),
                    "temp_c": current.get("temp_c"),
                    "feels_like_f": current.get("feelslike_f"),
                    "humidity": current.get("humidity"),
                    "wind_mph": current.get("wind_mph"),
                    "condition": current.get("condition", {}).get("text")
                },
                "forecast": condensed_forecast
            }
        except Exception as e:
            logger.error(f"[WeatherTool] Processing exception: {e}")
            return {"success": False, "error": str(e)}
