from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext
from backend.app.core.logging import logger
from backend.app.services.google.maps import google_maps_service

class MapsDirectionsInput(BaseModel):
    origin: str = Field(..., description="Starting address or landmark location.")
    destination: str = Field(..., description="Target destination address or landmark.")
    mode: str = Field("driving", description="Travel mode. Options: 'driving', 'walking', 'bicycling', 'transit'.")

class MapsDirectionsTool(BaseWingmanTool):
    """
    Performs high-level direction matrix queries. 
    Yields navigation distance, normal estimated times, 
    traffic-aware duration windows, and major highway summaries.
    """
    name = "google_maps_directions"
    description = "Calculates driving distance, traffic-aware ETA, and optimal routes between two addresses."
    args_schema = MapsDirectionsInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        origin = args["origin"]
        destination = args["destination"]
        mode = args.get("mode", "driving")
        
        # Global Spatial Grounding Intercept
        implicit_keywords = {"here", "current", "me", "my location", "local", "now", "."}
        user_loc = context.metadata.get("location") if context.metadata else None
        
        from backend.app.graphs.execution.helpers import emit_telemetry
        from backend.app.telemetry.schemas import TelemetryEventType
        
        telemetry_state = {
            "trace_id": context.trace_id,
            "run_id": context.run_id,
            "session_id": "active-session"
        }

        if (not origin or origin.lower().strip() in implicit_keywords) and user_loc:
            lat = user_loc.get("latitude")
            lon = user_loc.get("longitude")
            if lat is not None and lon is not None:
                origin = f"{lat},{lon}"
                logger.info(f"[MapsTool] Injected user spatial origin: {origin}")
                await emit_telemetry(
                    telemetry_state,
                    TelemetryEventType.SPATIAL_RESOLVED,
                    tool_name=self.name,
                    payload={
                        "original_query": args["origin"],
                        "resolved_coordinates": f"{lat:.4f}, {lon:.4f}",
                        "parameter": "origin"
                    }
                )

        logger.info(f"[MapsTool] Computing routing parameters: {origin} -> {destination} via {mode}")
        
        try:
            result = await google_maps_service.get_directions(
                origin=origin,
                destination=destination,
                mode=mode
            )
            
            await emit_telemetry(
                telemetry_state,
                TelemetryEventType.ROUTING_CALCULATED,
                tool_name=self.name,
                payload={"origin": origin, "destination": destination, "mode": mode}
            )
            
            import urllib.parse
            encoded_origin = urllib.parse.quote(str(origin))
            encoded_destination = urllib.parse.quote(str(destination))
            nav_url = f"https://www.google.com/maps/dir/?api=1&origin={encoded_origin}&destination={encoded_destination}&travelmode={mode}"

            if result.get("simulated", False):
                leg = result["routes"][0]["legs"][0]
                return {
                    "success": True,
                    "is_simulation": True,
                    "origin": leg["start_address"],
                    "destination": leg["end_address"],
                    "distance": leg["distance"]["text"],
                    "duration": leg["duration"]["text"],
                    "duration_in_traffic": leg["duration_in_traffic"]["text"],
                    "summary": result["routes"][0]["summary"],
                    "navigation_url": nav_url,
                    "notice": "Using simulated fallback. Please configure a valid GOOGLE_MAPS_API_KEY."
                }

            if not result.get("success", False):
                return {
                    "success": False,
                    "error": result.get("message", "API returned unresolvable routing payload.")
                }

            data = result["data"]
            routes = data.get("routes", [])
            if not routes:
                return {"success": False, "error": "No viable paths found between locations."}

            # Focus on the primary/recommended route
            primary_route = routes[0]
            leg = primary_route["legs"][0]
            
            response_payload = {
                "success": True,
                "origin": leg.get("start_address"),
                "destination": leg.get("end_address"),
                "distance": leg.get("distance", {}).get("text"),
                "duration": leg.get("duration", {}).get("text"),
                "summary": primary_route.get("summary", "Main Route"),
                "navigation_url": nav_url,
            }
            
            # Add traffic ETA if available
            if "duration_in_traffic" in leg:
                response_payload["duration_in_traffic"] = leg["duration_in_traffic"]["text"]

            logger.info(f"[MapsTool] Routing succeeded. Distance={response_payload['distance']}")
            return response_payload

        except Exception as e:
            logger.error(f"[MapsTool] Execution failure: {e}")
            return {"success": False, "error": str(e)}


class MapsNearbyInput(BaseModel):
    query: str = Field(..., description="Search keyword (e.g., 'coffee shops', 'hospitals', 'grocery store').")
    location: str = Field("current", description="Center coordinates or address. Use 'current' to leverage user's dynamic geolocation context.")
    radius: int = Field(5000, description="Boundary radius in meters (defaults to 5000).")

class MapsNearbySearchTool(BaseWingmanTool):
    """
    Performs robust nearby search matrices querying the Google Places API suite.
    Locates commercial hubs, services, transit points, and recreational areas 
    relative to absolute user location context coordinates.
    """
    name = "google_maps_nearby_search"
    description = "Finds nearby entities, shops, or local places based on search criteria and spatial user context."
    args_schema = MapsNearbyInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        query = args["query"]
        loc = args.get("location", "current")
        radius = min(max(args.get("radius", 5000), 200), 50000)
        
        implicit_keywords = {"here", "current", "me", "my location", "local", "."}
        user_loc = context.metadata.get("location") if context.metadata else None
        
        from backend.app.graphs.execution.helpers import emit_telemetry
        from backend.app.telemetry.schemas import TelemetryEventType
        
        telemetry_state = {
            "trace_id": context.trace_id,
            "run_id": context.run_id,
            "session_id": "active-session"
        }

        if (not loc or loc.lower().strip() in implicit_keywords) and user_loc:
            lat = user_loc.get("latitude")
            lon = user_loc.get("longitude")
            if lat is not None and lon is not None:
                loc = f"{lat},{lon}"
                logger.info(f"[MapsNearby] Grounded spatial lookup around coordinate anchor: {loc}")
                await emit_telemetry(
                    telemetry_state,
                    TelemetryEventType.SPATIAL_RESOLVED,
                    tool_name=self.name,
                    payload={
                        "original_query": args.get("location", "current"),
                        "resolved_coordinates": f"{lat:.4f}, {lon:.4f}",
                        "parameter": "location"
                    }
                )

        if loc.lower().strip() in implicit_keywords:
            return {
                "success": False, 
                "error": "Target requested current location but active user spatial context is unavailable. Prompt user to share location."
            }

        logger.info(f"[MapsNearby] Running search for '{query}' around '{loc}' within {radius}m.")
        
        try:
            result = await google_maps_service.get_nearby_places(
                query=query,
                location=loc,
                radius_meters=radius
            )
            
            await emit_telemetry(
                telemetry_state,
                TelemetryEventType.NEARBY_SEARCHED,
                tool_name=self.name,
                payload={"query": query, "center": loc, "radius_meters": radius}
            )
            
            if result.get("simulated", False):
                return {
                    "success": True,
                    "is_simulation": True,
                    "results": result["results"],
                    "notice": "Using simulated fallback. Please configure a valid GOOGLE_MAPS_API_KEY."
                }

            if not result.get("success", False):
                return {
                    "success": False,
                    "error": result.get("message", "API error searching nearby places.")
                }

            data = result["data"]
            raw_places = data.get("results", [])
            places = []
            for item in raw_places[:10]:
                places.append({
                    "name": item.get("name"),
                    "address": item.get("vicinity"),
                    "rating": item.get("rating"),
                    "user_ratings": item.get("user_ratings_total"),
                    "types": item.get("types", [])[:3]
                })

            logger.info(f"[MapsNearby] Discovered {len(places)} results.")
            return {
                "success": True,
                "results": places
            }

        except Exception as e:
            logger.error(f"[MapsTool] Nearby search execution failure: {e}")
            return {"success": False, "error": str(e)}
