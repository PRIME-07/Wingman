from typing import Any, Dict, Optional
from datetime import datetime
import pytz
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext

class ClockInput(BaseModel):
    format: Optional[str] = Field(
        default="%Y-%m-%d %H:%M:%S %Z", 
        description="Optional strftime format to override the default string output."
    )

class ClockTool(BaseWingmanTool):
    """
    Retrieves highly accurate current datetime context mapped dynamically 
    to the requested timezone or User preference defaults.
    """
    name = "clock_utility"
    description = "Get current system and human-readable dates, times, and active user timezone offsets."
    args_schema = ClockInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        tz_str = context.user_timezone or "UTC"
        fmt = args.get("format", "%Y-%m-%d %H:%M:%S %Z")
        
        try:
            tz = pytz.timezone(tz_str)
        except Exception:
            tz = pytz.UTC
            tz_str = "UTC"
            
        now = datetime.now(tz)
        
        return {
            "iso_format": now.isoformat(),
            "human_readable": now.strftime(fmt),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timezone": tz_str,
            "day_of_week": now.strftime("%A")
        }
