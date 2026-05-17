from typing import Dict
from backend.app.memory.mongodb_client import mongo_client
from backend.app.core.logging import logger

class ToolLatencyTracker:
    """
    Tracks running average latencies of tools dynamically using MongoDB storage.
    Enables real-time prediction metrics injected directly to AI planning contexts.
    """

    async def record_latency(self, tool_name: str, duration_ms: float) -> None:
        """Atomically records a running average calculation for latency analytics."""
        try:
            mongo_client.connect()
            coll = mongo_client.db["tool_latency_stats"]
            
            doc = await coll.find_one({"tool_name": tool_name})
            if doc:
                prev_avg = doc.get("average_latency_ms", duration_ms)
                prev_count = doc.get("sample_count", 1)
                
                # Moving average calculation
                new_count = prev_count + 1
                new_avg = ((prev_avg * prev_count) + duration_ms) / new_count
                
                await coll.update_one(
                    {"tool_name": tool_name},
                    {"$set": {"average_latency_ms": round(new_avg, 2), "sample_count": new_count}}
                )
            else:
                # First recording
                await coll.insert_one({
                    "tool_name": tool_name,
                    "average_latency_ms": round(duration_ms, 2),
                    "sample_count": 1
                })
        except Exception as e:
            logger.error(f"[LatencyTracker] Failed updating telemetry for '{tool_name}': {e}")

    async def get_all_latencies(self) -> Dict[str, float]:
        """Returns cached dict mapping {tool_name -> avg_latency_ms}."""
        try:
            mongo_client.connect()
            coll = mongo_client.db["tool_latency_stats"]
            cursor = coll.find({})
            
            latency_map = {}
            async for doc in cursor:
                latency_map[doc["tool_name"]] = doc["average_latency_ms"]
            return latency_map
        except Exception as e:
            logger.error(f"[LatencyTracker] Failed reading catalog stats: {e}")
            return {}

# Singleton instance
latency_tracker = ToolLatencyTracker()
