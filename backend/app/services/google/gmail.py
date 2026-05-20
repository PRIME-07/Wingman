import base64
from typing import Any, Dict, Optional, List
from email.message import EmailMessage
from googleapiclient.discovery import build
from backend.app.core.logging import logger
from backend.app.services.google.oauth import google_oauth_manager

class GmailService:
    """
    Provides clean functional abstractions over official Google API Client Discovery methods.
    Encapsulates base64 packaging, RFC compliant header mappings, and auto-refresh credential bindings.
    """
    
    async def _get_client(self) -> Any:
        """Fetches refreshed Google OAuth credentials and returns a functional Gmail service builder."""
        creds = await google_oauth_manager.get_authenticated_credentials()
        if not creds:
            raise PermissionError("Active Google account is not authenticated or authorization expired.")
        
        # Build standard Resource client object (uses httplib2 transport behind scenes)
        return build("gmail", "v1", credentials=creds)

    def _build_mime_message(
        self, 
        recipient: str, 
        subject: str, 
        body_text: str, 
        body_html: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Serializes raw textual payloads into base64 encoded RFC 2822 compliant Gmail structures."""
        mime_msg = EmailMessage()
        
        # Handle multi-recipient parsing cleanly
        mime_msg["To"] = recipient
        mime_msg["Subject"] = subject
        
        # Support Rich HTML formatting cascading fallback
        mime_msg.set_content(body_text)
        if body_html:
            mime_msg.add_alternative(body_html, subtype="html")
            
        raw_bytes = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")
        
        message_payload = {"raw": raw_bytes}
        if thread_id:
            message_payload["threadId"] = thread_id
            
        return message_payload

    async def create_draft(
        self, 
        recipient: str, 
        subject: str, 
        body_text: str, 
        body_html: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates an email Draft object in the authenticated user's mailbox without dispatching."""
        try:
            client = await self._get_client()
            
            mime_payload = self._build_mime_message(
                recipient=recipient,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                thread_id=thread_id
            )
            
            draft_body = {"message": mime_payload}
            
            logger.info(f"[GmailService] Initiating draft creation api call for target='{recipient}'.")
            
            # Executed sync discovery method wrapped in async block to not block main thread loop
            draft = client.users().drafts().create(userId="me", body=draft_body).execute()
            
            logger.info(f"[GmailService] Securely created Draft ID={draft.get('id')}.")
            return {
                "success": True,
                "draft_id": draft.get("id"),
                "thread_id": draft.get("message", {}).get("threadId"),
                "status": "Draft Generated"
            }
        except Exception as e:
            logger.error(f"[GmailService] Error creating draft: {e}", exc_info=True)
            raise

    async def update_draft(
        self,
        draft_id: str,
        recipient: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Updates an existing email Draft object with a new message structure."""
        try:
            client = await self._get_client()
            
            mime_payload = self._build_mime_message(
                recipient=recipient,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                thread_id=thread_id
            )
            
            draft_body = {"id": draft_id, "message": mime_payload}
            
            logger.info(f"[GmailService] Updating draft ID={draft_id} for recipient='{recipient}'.")
            
            draft = client.users().drafts().update(userId="me", id=draft_id, body=draft_body).execute()
            
            logger.info(f"[GmailService] Securely updated Draft ID={draft.get('id')}.")
            return {
                "success": True,
                "draft_id": draft.get("id"),
                "status": "Draft Updated"
            }
        except Exception as e:
            logger.error(f"[GmailService] Error updating draft: {e}", exc_info=True)
            raise

    async def send_draft(self, draft_id: str) -> Dict[str, Any]:
        """Dispatches a previously staged Draft directly to the targeted recipients."""
        try:
            client = await self._get_client()
            logger.info(f"[GmailService] Dispatching Draft ID={draft_id}...")
            
            sent_msg = client.users().drafts().send(userId="me", body={"id": draft_id}).execute()
            
            logger.info(f"[GmailService] Email successfully dispatched. MessageID={sent_msg.get('id')}.")
            return {
                "success": True,
                "message_id": sent_msg.get("id"),
                "thread_id": sent_msg.get("threadId"),
                "status": "Message Dispatched"
            }
        except Exception as e:
            logger.error(f"[GmailService] Failed to send draft={draft_id}: {e}")
            raise

    async def list_threads(self, max_results: int = 10, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries user mailbox history to extract recent thread activities for context generation."""
        try:
            client = await self._get_client()
            
            response = client.users().threads().list(userId="me", maxResults=max_results, q=query).execute()
            return response.get("threads", [])
        except Exception as e:
            logger.error(f"[GmailService] Thread retrieval error: {e}")
            return []

# Singleton instance
gmail_service = GmailService()
