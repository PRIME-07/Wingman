from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext, wingman_interrupt
from backend.app.core.logging import logger
from backend.app.services.google.gmail import gmail_service

class GmailDraftInput(BaseModel):
    recipient: str = Field(..., description="Target email address.")
    subject: str = Field(..., description="Heading of the email.")
    body: str = Field(..., description="Plain-text body of the email.")
    body_html: Optional[str] = Field(None, description="Optional Rich HTML payload of the email.")

class GmailDraftTool(BaseWingmanTool):
    """
    Coordinates standard transactional email dispatch. 
    1. Stages real Google API Draft.
    2. Suspends execution with LangGraph native interrupt to prompt human approval.
    3. Dispatches Draft strictly upon receipt of approved flag.
    """
    name = "gmail_draft"
    description = "Drafts an email. REQUIRES user review and explicit approval prior to dispatching email."
    args_schema = GmailDraftInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        recipient = args["recipient"]
        subject = args["subject"]
        body = args["body"]
        body_html = args.get("body_html")
        
        try:
            logger.info(f"[GmailTool] Generating real Google Mail Draft for recipient='{recipient}'.")
            
            # Step 1: Create the REAL draft on Google Servers
            draft_response = await gmail_service.create_draft(
                recipient=recipient,
                subject=subject,
                body_text=body,
                body_html=body_html
            )
            draft_id = draft_response["draft_id"]
            
            # Telemetry: draft_created status (will refine Base methods later, logging for now)
            logger.info(f"[GmailTool] Draft {draft_id} staged. Issuing LangGraph Interrupt.")
            
            # Step 2: Halt runtime context and prompt UI dashboard
            human_decision = wingman_interrupt({
                "tool": "gmail_draft",
                "prompt": f"Review pending email to {recipient}.",
                "data": {
                    "draft_id": draft_id,
                    "recipient": recipient,
                    "subject": subject,
                    "body": body,
                    "body_html": body_html
                }
            }, context)
            
            # Step 3: Evaluate approval state
            is_approved = human_decision.get("approved", False)
            
            if is_approved:
                # Support user manual edits prior to dispatch
                final_recipient = human_decision.get("recipient", recipient)
                final_subject = human_decision.get("subject", subject)
                final_body = human_decision.get("body", body)
                final_body_html = human_decision.get("body_html", body_html)
                
                if (final_recipient != recipient or 
                    final_subject != subject or 
                    final_body != body or 
                    final_body_html != body_html):
                    logger.info(f"[GmailTool] Custom modifications detected in HITL. Updating draft {draft_id}.")
                    update_res = await gmail_service.update_draft(
                        draft_id=draft_id,
                        recipient=final_recipient,
                        subject=final_subject,
                        body_text=final_body,
                        body_html=final_body_html
                    )
                    draft_id = update_res.get("draft_id", draft_id)
                    recipient = final_recipient
                    subject = final_subject

                logger.info(f"[GmailTool] Approval received for DraftID={draft_id}. Executing send.")
                send_result = await gmail_service.send_draft(draft_id)
                
                return {
                    "status": "Email Sent Successfully",
                    "message_id": send_result["message_id"],
                    "recipient": recipient,
                    "subject": subject
                }
            else:
                # Rejection or Refinement scenario
                reason = human_decision.get("reason", "User cancelled the action.")
                refine = human_decision.get("refine", False)
                
                if refine:
                    logger.warning(f"[GmailTool] Email Draft {draft_id} REFINE requested by user. Feedback: {reason}")
                    return {
                        "status": "Refine Requested",
                        "reason": reason,
                        "draft_id": draft_id,
                        "instruction": f"The user requested changes to the draft. Feedback: '{reason}'. You MUST revise the text and recipient details and call the gmail_draft tool again with the updated arguments to present the revised draft to the user."
                    }
                else:
                    logger.warning(f"[GmailTool] Email Draft {draft_id} REJECTED by user. Reason: {reason}")
                    return {
                        "status": "Rejected",
                        "reason": reason,
                        "draft_id": draft_id,
                        "instruction": "The user rejected sending this draft. Revise the text or ask user for clarification based on the feedback reasoning."
                    }
                
        except PermissionError as pe:
            logger.error(f"[GmailTool] Authentication error: {pe}")
            return {
                "status": "Auth Failure",
                "error": str(pe),
                "instruction": "Authorize Google credentials via /api/v1/auth/google/connect first."
            }
        except Exception as e:
            logger.error(f"[GmailTool] Unexpected api error: {e}", exc_info=True)
            raise

