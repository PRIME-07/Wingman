import os
import aiohttp
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext
from backend.app.core.logging import logger
from backend.app.core.config import settings
from backend.app.services.credentials.manager import credential_manager

class WebSearchInput(BaseModel):
    query: str = Field(..., description="The exact string query search parameter.")
    num_results: int = Field(default=3, description="Limits returned dataset references.")

class WebSearchTool(BaseWingmanTool):
    """
    Searches the internet dynamically for real-time knowledge retrieval using Tavily API.
    Falls back gracefully to mock data if the API key is unavailable or invalid.
    """
    name = "web_search"
    description = "Executes robust web lookups to fetch the latest online real-world events or answers."
    args_schema = WebSearchInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> List[Dict[str, str]]:
        query = args["query"]
        num_results = min(max(args.get("num_results", 3), 1), 10)
        
        # Safely acquire API key from active environment or settings
        api_key = await credential_manager.get_secret("tavily_api_key", provider="tools")
        
        if not api_key or "tvly-" not in api_key:
            logger.warning("[WebSearchTool] TAVILY_API_KEY not provided. Serving fallback stub dataset.")
            return self._get_stub_data(query)

        logger.info(f"[WebSearchTool] Dispatching live search query across Tavily indexed web: '{query}'")
        
        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": api_key,
                "query": query,
                "max_results": num_results
            }
            
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        raw_err = await resp.text()
                        logger.warning(f"[WebSearchTool] Provider query failed status={resp.status}: {raw_err}")
                        return self._get_stub_data(query)
                    
                    res_payload = await resp.json()
                    results = res_payload.get("results", [])
                    
                    compiled_results = []
                    for item in results:
                        compiled_results.append({
                            "title": item.get("title", "Search Result"),
                            "snippet": item.get("content", "Result details not provided."),
                            "source": item.get("url", "https://example.com")
                        })
                    
                    logger.info(f"[WebSearchTool] Found {len(compiled_results)} active references.")
                    return compiled_results
                    
        except Exception as e:
            logger.error(f"[WebSearchTool] Network transaction failed: {e}")
            return self._get_stub_data(query)

    def _get_stub_data(self, query: str) -> List[Dict[str, str]]:
        """Consistently returns the fallback MVP search snippet."""
        return [
            {
                "title": f"Search snippet: {query}",
                "snippet": f"Here is a relevant snippet simulating actual search engine output containing the answer for '{query}'...",
                "source": "https://example.com/search"
            },
            {
                "title": "Developer Knowledge Base",
                "snippet": "Integration with Tavily/Bing API requested for production workloads.",
                "source": "https://docs.wingman.ai"
            }
        ]
