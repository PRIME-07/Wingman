from typing import List, Dict, Any
from pydantic import BaseModel, Field

class DelegateToWebAgentSchema(BaseModel):
    query: str = Field(description="The specific search query or instruction for the web agent.")

class DelegateToCommAgentSchema(BaseModel):
    request: str = Field(description="The communication task, such as drafting an email or sending a Slack message.")

class DelegateToWorkAgentSchema(BaseModel):
    request: str = Field(description="The workspace task, like calendar scheduling, docs editing, alarms, or maps directions.")

class DelegateToRagAgentSchema(BaseModel):
    query: str = Field(description="The specific query to search within user-uploaded documents and internal memory.")

def get_delegation_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "delegate_to_web_agent",
                "description": "Delegate a task to the Web Research Agent. Useful for searching the internet, finding documentation, news, or any real-time external information. DO NOT use this for weather queries.",
                "parameters": DelegateToWebAgentSchema.model_json_schema()
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delegate_to_comm_agent",
                "description": "Delegate a task to the Communication Agent. Useful for sending emails, reading emails, drafting Slack messages, or reading Slack channels.",
                "parameters": DelegateToCommAgentSchema.model_json_schema()
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delegate_to_work_agent",
                "description": "Delegate a task to the Workspace Agent. MUST be used for getting live weather, scheduling calendar events, managing Google Docs and Sheets, setting timers/alarms, and getting directions.",
                "parameters": DelegateToWorkAgentSchema.model_json_schema()
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delegate_to_rag_agent",
                "description": "Delegate a task to the Knowledge Agent. Useful for searching user-uploaded documents and finding internal context.",
                "parameters": DelegateToRagAgentSchema.model_json_schema()
            }
        }
    ]
