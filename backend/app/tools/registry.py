from typing import Dict, List, Type, Any
from backend.app.tools.base.interface import BaseWingmanTool
from backend.app.tools.clock.tool import ClockTool
from backend.app.tools.clock.timer_tool import TimerSetTool, TimerCancelTool, TimerListTool
from backend.app.tools.clock.reminder_tool import ReminderTool
from backend.app.tools.websearch.tool import WebSearchTool

from backend.app.tools.memory.tool import MemoryRetrievalTool
from backend.app.tools.gmail.tool import GmailDraftTool
from backend.app.tools.slack.tool import SlackDraftTool, SlackChannelListTool
from backend.app.tools.calendar.tool import CalendarScheduleTool, CalendarQueryTool, CalendarModifyTool, CalendarDeleteTool, CalendarBatchScheduleTool, CalendarBatchModifyTool, CalendarBatchDeleteTool

from backend.app.tools.google_docs.tool import DocsCreateTool, DocsReadTool, DocsEditTool, DocsSearchTool
from backend.app.tools.google_sheets.tool import SheetsCreateTool, SheetsReadTool, SheetsAppendTool, SheetsUpdateTool, SheetsSearchTool
from backend.app.tools.google_maps.tool import MapsDirectionsTool, MapsNearbySearchTool
from backend.app.tools.weather.tool import WeatherQueryTool
from backend.app.tools.youtube.tool import YoutubeSearchTool
from backend.app.tools.rag.tool import DocumentRAGTool

class ToolRegistry:
    """
    Main registry storing and mapping custom assistant tool definitions.
    Supports unified lookup, serialization, and integration with model interfaces.
    """
    def __init__(self):
        self._tools: Dict[str, BaseWingmanTool] = {}
        self._register_defaults()

    def register(self, tool: BaseWingmanTool):
        """Registers a tool instance into the mapping."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseWingmanTool:
        """Retrieves an instantiated tool definition."""
        if name not in self._tools:
            raise ValueError(f"Requested tool '{name}' is not registered.")
        return self._tools[name]

    def list_tools(self) -> List[BaseWingmanTool]:
        """Lists all initialized assistant tools."""
        return list(self._tools.values())

    def get_openai_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Serializes all registered tools into standard OpenAI Function calling schemas
        by utilizing Pydantic model_json_schema generations automatically.
        """
        schemas = []
        for tool in self.list_tools():
            param_schema = {}
            if tool.args_schema:
                param_schema = tool.args_schema.model_json_schema()
                # Strip out title artifacts added by Pydantic
                param_schema.pop("title", None)
                if "properties" in param_schema:
                    for p in param_schema["properties"].values():
                        p.pop("title", None)
            else:
                param_schema = {"type": "object", "properties": {}}
                
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": param_schema
                }
            })
        return schemas

    def _register_defaults(self):
        """Auto-initializes required MVP tooling modules."""
        self.register(ClockTool())
        self.register(TimerSetTool())
        self.register(TimerCancelTool())
        self.register(TimerListTool())
        self.register(ReminderTool())
        self.register(WebSearchTool())

        self.register(MemoryRetrievalTool())
        self.register(GmailDraftTool())
        self.register(SlackDraftTool())
        self.register(SlackChannelListTool())
        self.register(CalendarScheduleTool())
        self.register(CalendarQueryTool())
        self.register(CalendarModifyTool())
        self.register(CalendarDeleteTool())
        self.register(CalendarBatchScheduleTool())
        self.register(CalendarBatchModifyTool())
        self.register(CalendarBatchDeleteTool())
        self.register(DocsCreateTool())
        self.register(DocsReadTool())
        self.register(DocsEditTool())
        self.register(DocsSearchTool())
        self.register(SheetsCreateTool())
        self.register(SheetsReadTool())
        self.register(SheetsAppendTool())
        self.register(SheetsUpdateTool())
        self.register(SheetsSearchTool())
        self.register(MapsDirectionsTool())
        self.register(MapsNearbySearchTool())
        self.register(WeatherQueryTool())
        self.register(YoutubeSearchTool())
        self.register(DocumentRAGTool())
        
        # Contacts Tools
        from backend.app.tools.contacts.tool import ContactsSearchTool, ContactsCreateTool
        self.register(ContactsSearchTool())
        self.register(ContactsCreateTool())







# Singleton access provider
tool_registry = ToolRegistry()
