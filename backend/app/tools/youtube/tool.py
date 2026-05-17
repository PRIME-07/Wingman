from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext
from backend.app.core.logging import logger
from backend.app.services.youtube.service import youtube_service

class YoutubeSearchInput(BaseModel):
    query: str = Field(..., description="Search keywords or subject text to query on YouTube.")
    max_results: int = Field(5, description="Number of videos to return.")

class YoutubeSearchTool(BaseWingmanTool):
    """
    Executes public YouTube Data queries.
    Collects high-quality videos matching input parameters, including URLs, descriptions, 
    publish dates, and originating channels.
    """
    name = "youtube_search"
    description = "Searches YouTube for videos on a given subject and returns titles, links, and summaries."
    args_schema = YoutubeSearchInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        q = args["query"]
        limit = args.get("max_results", 5)
        
        logger.info(f"[YoutubeTool] Locating related media for: '{q}'")
        
        try:
            res = await youtube_service.search_videos(q, limit)
            
            is_simulated = res.get("simulated", False)
            items = res["items"] if is_simulated else res["data"].get("items", [])
            
            # Compile condensed structured list
            output_videos = []
            for item in items:
                vid_id = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                if vid_id:
                    output_videos.append({
                        "title": snippet.get("title"),
                        "channel": snippet.get("channelTitle"),
                        "published_at": snippet.get("publishedAt"),
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                        "description": snippet.get("description")
                    })

            logger.info(f"[YoutubeTool] Found {len(output_videos)} matching videos for analysis.")
            return {
                "success": True,
                "is_simulation": is_simulated,
                "videos": output_videos,
                "summary": f"Retrieved {len(output_videos)} video matches."
            }
        except Exception as e:
            logger.error(f"[YoutubeTool] Search operation failing: {e}")
            return {"success": False, "error": str(e)}
