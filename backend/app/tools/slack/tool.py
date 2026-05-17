from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext, wingman_interrupt
from backend.app.core.logging import logger
from backend.app.services.slack.service import slack_service

# Tool 1: Send/Draft Message (Requires HITL)

class SlackDraftInput(BaseModel):
    channel: str = Field(..., description="Name or Unique ID of target Slack channel.")
    message: str = Field(..., description="Text payload or markdown format message string.")

class SlackDraftTool(BaseWingmanTool):
    """
    Prepares an outbound Slack communication.
    Enforces manual Human-in-the-Loop validation prior to finalizing network delivery.
    """
    name = "slack_draft"
    description = "Drafts a message to Slack. REQUIRES manual user review and approval before dispatch."
    args_schema = SlackDraftInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        channel = args["channel"]
        message = args["message"]
        
        logger.info(f"[SlackTool] Injecting interactive interrupt loop for Slack post targeting '{channel}'.")
        
        # Suspend Graph State to wait for browser or push confirmation
        decision = wingman_interrupt({
            "tool": "slack_draft",
            "prompt": f"Send Message to {channel}?",
            "data": {
                "channel": channel,
                "message": message
            }
        }, context)
        
            # Capture User action injection
        if decision.get("approved", False) is True:
            # Extract possible user overrides from decision dict
            final_channel = decision.get("channel", channel)
            final_message = decision.get("message", message)
            
            logger.info(f"[SlackTool] Approval validated. Inspecting routing gateway for {final_channel}...")
            
            try:
                # 1. Identify if targeting DM vs Channel Channel
                is_dm = False
                target_clean = final_channel.strip()
                
                if target_clean.startswith("@") or (target_clean.startswith("U") and len(target_clean) >= 9):
                    is_dm = True
                elif target_clean.lower() in ["me", "dm", "direct", "private"]:
                    is_dm = True
                
                if is_dm:
                    recipient = target_clean.lstrip("@")
                    # Standardize user-centric defaults
                    if recipient.lower() in ["me", "dm", "direct", "private"]:
                        recipient = "Anuj Mankumare"
                        
                    logger.info(f"[SlackTool] Gateway routing direct message to recipient: '{recipient}'...")
                    response = await slack_service.send_dm(recipient=recipient, message=final_message, context=context)
                    return {
                        "success": True,
                        "status": "Message Posted Successfully",
                        "timestamp": response["ts"],
                        "channel": response["channel"],
                        "recipient_id": response.get("recipient_user_id")
                    }
                else:
                    logger.info(f"[SlackTool] Gateway routing public channel broadcast to: '{final_channel}'...")
                    response = await slack_service.post_message(channel=final_channel, text=final_message)
                    return {
                        "success": True,
                        "status": "Message Posted Successfully",
                        "timestamp": response["ts"],
                        "channel": response["channel"]
                    }
            except Exception as e:
                logger.error(f"[SlackTool] Slack delivery failed post-approval: {e}")
                err_msg = str(e)
                reason = err_msg
                if "missing_scope" in err_msg:
                    reason = "Slack DM permissions unavailable"
                elif "invalid_auth" in err_msg or "token" in err_msg.lower():
                    reason = "Slack workspace credentials invalid"
                    
                return {
                    "success": False,
                    "authenticity": "FAILED",
                    "reason": reason,
                    "status": "Error",
                    "error": err_msg
                }
        else:
            reason = decision.get("reason", "User declined action.")
            logger.warning(f"[SlackTool] Slack post rejected by operator: {reason}")
            return {
                "success": False,
                "status": "Rejected",
                "reason": reason,
                "instruction": "User cancelled posting. Ask if they wish to refine content."
            }


# Tool 2: Channel Discover (Safe)

class SlackChannelListInput(BaseModel):
    limit: int = Field(50, description="Max number of items to query.")

class SlackChannelListTool(BaseWingmanTool):
    """
    Fetches lists of accessible Slack channels in the workspace.
    Allows Wingman to correctly map casual channel names to exact IDs.
    """
    name = "slack_channels_list"
    description = "Lists accessible Slack channels in the connected workspace."
    args_schema = SlackChannelListInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        try:
            res = await slack_service.list_channels(limit=args["limit"])
            channels_list = res.get("channels", [])
            
            # Extract concise records to optimize agent prompt space
            records = []
            for c in channels_list:
                records.append({
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "is_private": c.get("is_private", False),
                    "topic": c.get("topic", {}).get("value") if isinstance(c.get("topic"), dict) else None
                })
                
            logger.info(f"[SlackTool] Located {len(records)} workspace channels.")
            return {
                "success": True,
                "channels": records,
                "summary": f"Identified {len(records)} channels."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

