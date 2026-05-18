from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
from slack_sdk.web.async_client import AsyncWebClient
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.services.credentials.manager import credential_manager
from backend.app.memory.mongodb_client import mongo_client
from backend.app.telemetry.schemas import TelemetryEventType

if TYPE_CHECKING:
    from backend.app.tools.base.interface import ToolExecutionContext

class SlackService:
    """
    Interfaces with Slack SDK Async WebClients.
    Pulls encrypted workspace configurations via CredentialManager.
    Supports channel enumeration and block-formatted messaging.
    """

    async def _get_token(self) -> Optional[str]:
        """
        Extracts active bot token from persistent encrypted storage.
        Falls back to bootstrap configuration values.
        """
        token = await credential_manager.get_secret("slack_bot_token", provider="slack")
        if token and "xoxb" in token:
            return token
            
        return None

    async def _get_client(self) -> AsyncWebClient:
        """Constructs validated Slack SDK connection runner."""
        token = await self._get_token()
        if not token:
            raise PermissionError("Slack integration not configured. Please define SLACK_BOT_TOKEN.")
        return AsyncWebClient(token=token)

    async def post_message(
        self, 
        channel: str, 
        text: str, 
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Dispatches a real message payload to a targeted Channel or direct thread.
        Accepts optional Slack-native Block Kit UI definitions for advanced rich formatting.
        """
        try:
            client = await self._get_client()
            
            # A. Resolve Target (DM or Channel) to valid ID if not provided
            target_id = channel
            clean_name = channel.lstrip("#@").strip()
            
            # Special indicators of a User target (DM)
            is_user_target = channel.startswith("@") or channel.lower() in ["me", "dm", "direct message"]
            # IDs generally start with C (channel), G (group), D (DM), or U (user) and are long enough
            is_id = channel.startswith(("C", "G", "D", "U")) and len(channel) >= 9
            
            if not is_id:
                if is_user_target:
                    lookup_name = clean_name
                    if lookup_name.lower() in ["me", "dm", "direct message"]:
                        lookup_name = "Anuj Mankumare" # Map default user to current environment persona
                    
                    resolved_uid = await self._resolve_user_to_id(client, lookup_name)
                    if resolved_uid:
                        target_id = resolved_uid
                        logger.info(f"[SlackService] Mapped user target '{channel}' -> User ID '{target_id}'")
                else:
                    # Standard Channel name resolution
                    logger.info(f"[SlackService] Resolving channel name '{clean_name}' to ID...")
                    try:
                        res = await self.list_channels()
                        if res.get("success") and not res.get("simulated"):
                            for c in res.get("channels", []):
                                if c.get("name") == clean_name or c.get("id") == clean_name:
                                    target_id = c["id"]
                                    logger.info(f"[SlackService] Mapped channel name '{channel}' -> ID '{target_id}'")
                                    break
                    except Exception as list_err:
                        logger.warning(f"[SlackService] Resolution query failed: {list_err}. Proceeding with raw identifier.")
            
            # B. Dispatch Message with Proactive Auto-Join Fallback
            logger.info(f"[SlackService] Dispatching chat transmission to target='{target_id}'...")
            try:
                response = await client.chat_postMessage(
                    channel=target_id,
                    text=text,
                    blocks=blocks
                )
            except Exception as e:
                err_str = str(e).lower()
                if "not_in_channel" in err_str:
                    logger.info(f"[SlackService] Bot not in channel {target_id}. Attempting automatic join...")
                    try:
                        # Public channels can be joined via API. If it fails (e.g. private), we raise original.
                        await client.conversations_join(channel=target_id)
                        logger.info("[SlackService] Joined channel successfully. Retrying message dispatch...")
                        response = await client.chat_postMessage(
                            channel=target_id,
                            text=text,
                            blocks=blocks
                        )
                    except Exception as join_err:
                        logger.error(f"[SlackService] Automatic channel join or dispatch retry failed: {join_err}")
                        raise e
                else:
                    raise e
            
            if response["ok"]:
                logger.info(f"[SlackService] Success! TS={response.get('ts')}")
                return {
                    "success": True,
                    "ts": response.get("ts"),
                    "channel": response.get("channel")
                }
                
            raise RuntimeError(f"Slack delivery failure: {response.get('error')}")
            
        except PermissionError as e:
            # Simulation only triggers if integrations are totally unconfigured
            logger.warning(f"[SlackService] Slack integration unconfigured ({e}). Running simulation post.")
            return {
                "success": True,
                "simulated": True,
                "ts": "1715600000.000000",
                "channel": channel,
                "message": "Simulated post succeeded."
            }
        except Exception as e:
            # Expose real API failures so Wingman can communicate real errors to the user
            logger.error(f"[SlackService] Real Slack API operation failed: {e}")
            raise e

    async def _resolve_user_to_id(self, client: AsyncWebClient, name: str) -> Optional[str]:
        """Resolves a username, display name, or real name to their internal Slack User ID."""
        clean = name.lstrip("@").strip().lower()
        logger.info(f"[SlackService] Resolving username/name '{clean}' to User ID...")
        try:
            response = await client.users_list()
            if response["ok"]:
                members = response.get("members", [])
                # Priority 1: Exact matches on name, real name, or display name
                for m in members:
                    if m.get("deleted") or m.get("is_bot"):
                        continue
                    
                    uname = str(m.get("name", "")).lower()
                    dname = str(m.get("profile", {}).get("display_name", "")).lower()
                    rname = str(m.get("profile", {}).get("real_name", "")).lower()
                    
                    if clean in (uname, dname, rname):
                        return m["id"]
                
                # Priority 2: Fuzzy partial matches (e.g. "anuj" matches "anuj mankumare")
                for m in members:
                    if m.get("deleted") or m.get("is_bot"):
                        continue
                    
                    uname = str(m.get("name", "")).lower()
                    dname = str(m.get("profile", {}).get("display_name", "")).lower()
                    rname = str(m.get("profile", {}).get("real_name", "")).lower()
                    
                    if clean in uname or clean in dname or clean in rname:
                        return m["id"]
        except Exception as e:
            logger.warning(f"[SlackService] Dynamic user resolution query failed: {e}. Make sure Slack bot has 'users:read' scope.")
        return None

    async def list_channels(self, types: str = "public_channel,private_channel", limit: int = 100) -> Dict[str, Any]:
        """Queries the active workspace context to discover accessible channels."""
        try:
            client = await self._get_client()
            
            logger.info("[SlackService] Listing workspace channels...")
            response = await client.conversations_list(types=types, limit=limit)
            
            if response["ok"]:
                return {
                    "success": True,
                    "channels": response.get("channels", [])
                }
                
            raise RuntimeError(f"Slack channel query failure: {response.get('error')}")
        except PermissionError as e:
            logger.warning(f"[SlackService] Slack lookup bypassed ({e}). Returning simulation channels.")
            # Restructure to match test expected schemas
            return {
                "success": True,
                "simulated": True,
                "channels": [
                    {"id": "C0123456789", "name": "general", "is_member": True},
                    {"id": "C0987654321", "name": "engineering", "is_member": True},
                    {"id": "C1122334455", "name": "alerts", "is_member": False}
                ]
            }
        except Exception as e:
            logger.error(f"[SlackService] Real Slack API lookup failed: {e}")
            raise e

    async def _emit_slack_telemetry(
        self,
        event_type: TelemetryEventType,
        context: Optional["ToolExecutionContext"],
        payload: Dict[str, Any]
    ):
        """Helper to publish decoupled tracing events to developer streams."""
        if not context:
            return
        try:
            from backend.app.event_bus.bus import event_bus, EventPriority
            from backend.app.telemetry.schemas import TelemetryEvent
            
            event = TelemetryEvent(
                event_type=event_type,
                trace_id=context.trace_id,
                run_id=context.run_id,
                timestamp=datetime.utcnow(),
                node_name="comm_agent",
                tool_name="slack_draft",
                payload=payload
            )
            await event_bus.publish("telemetry", event, priority=EventPriority.NORMAL)
        except Exception as e:
            logger.warning(f"[SlackService] Telemetry event failed to emit: {e}")

    async def resolve_user(self, identifier: str, context: Optional["ToolExecutionContext"] = None) -> Optional[Dict[str, Any]]:
        """
        Resolves the best matching Slack user identity from the workspace directory.
        Prioritizes email-based matching, falling back to display name or real name.
        """
        try:
            client = await self._get_client()
            clean = identifier.lstrip("@").strip().lower()
            
            logger.info(f"[SlackService] Crawling workspace to resolve user identity matching '{clean}'...")
            response = await client.users_list()
            
            if not response.get("ok"):
                raise RuntimeError(f"Users API responded negatively: {response.get('error')}")
                
            members = response.get("members", [])
            resolved_user = None
            
            # Rule 1: Strong match - Email (Highly reliable)
            for m in members:
                if m.get("deleted") or m.get("is_bot"):
                    continue
                prof = m.get("profile", {})
                email = str(prof.get("email", "")).lower()
                if email == clean:
                    resolved_user = m
                    logger.info(f"[SlackService] High-confidence match found via Email -> User '{m.get('id')}'")
                    break
            
            # Rule 2: Exact display_name or real_name match
            if not resolved_user:
                for m in members:
                    if m.get("deleted") or m.get("is_bot"):
                        continue
                    prof = m.get("profile", {})
                    uname = str(m.get("name", "")).lower()
                    dname = str(prof.get("display_name", "")).lower()
                    rname = str(prof.get("real_name", "")).lower()
                    
                    if clean in (uname, dname, rname):
                        resolved_user = m
                        logger.info(f"[SlackService] Exact match found via identity tokens -> User '{m.get('id')}'")
                        break
                        
            # Rule 3: Fuzzy substring match (Fallback)
            if not resolved_user:
                for m in members:
                    if m.get("deleted") or m.get("is_bot"):
                        continue
                    prof = m.get("profile", {})
                    uname = str(m.get("name", "")).lower()
                    dname = str(prof.get("display_name", "")).lower()
                    rname = str(prof.get("real_name", "")).lower()
                    
                    if clean in uname or clean in dname or clean in rname:
                        resolved_user = m
                        logger.info(f"[SlackService] Fuzzy match found via identifiers -> User '{m.get('id')}'")
                        break

            if resolved_user:
                prof = resolved_user.get("profile", {})
                result = {
                    "user_id": resolved_user["id"],
                    "display_name": prof.get("display_name") or resolved_user.get("name"),
                    "real_name": prof.get("real_name"),
                    "email": prof.get("email")
                }
                
                await self._emit_slack_telemetry(
                    TelemetryEventType.SLACK_USER_RESOLVED,
                    context,
                    {"identifier": identifier, "resolved_id": result["user_id"]}
                )
                return result
                
        except Exception as e:
            logger.error(f"[SlackService] User resolution pipeline encountered a failure: {e}")
            raise e
            
        return None

    async def open_dm_channel(self, user_id: str, context: Optional["ToolExecutionContext"] = None) -> Dict[str, Any]:
        """Forces Slack to establish a fresh private conversation/IM channel with the user."""
        try:
            client = await self._get_client()
            logger.info(f"[SlackService] Executing API handshake to open direct conversation channel with user='{user_id}'...")
            
            response = await client.conversations_open(users=[user_id])
            if response.get("ok"):
                channel_id = response.get("channel", {}).get("id")
                logger.info(f"[SlackService] Conversational gateway successfully established. ChannelID={channel_id}")
                
                await self._emit_slack_telemetry(
                    TelemetryEventType.SLACK_DM_OPENED,
                    context,
                    {"user_id": user_id, "channel_id": channel_id}
                )
                return {"channel_id": channel_id}
                
            raise RuntimeError(f"Slack handshake failed to open conversation: {response.get('error')}")
        except Exception as e:
            logger.error(f"[SlackService] Failed to open direct message channel: {e}")
            raise e

    async def get_or_create_dm_channel(self, user_id: str, user_data: Dict[str, Any], context: Optional["ToolExecutionContext"] = None) -> str:
        """ Retrieves DM channel ID from persistent Mongo cache or spawns a new one on miss."""
        mongo_client.connect()
        cache_coll = mongo_client.db["slack_identity_cache"]
        
        # A. Persistent Cache Lookup
        try:
            cached_entry = await cache_coll.find_one({"slack_user_id": user_id})
            if cached_entry and cached_entry.get("dm_channel_id"):
                logger.info(f"[SlackService] CACHE HIT: Found persisted DM routing entry for user={user_id} -> {cached_entry['dm_channel_id']}")
                
                await self._emit_slack_telemetry(
                    TelemetryEventType.SLACK_DM_CACHE_HIT,
                    context,
                    {"user_id": user_id, "channel_id": cached_entry["dm_channel_id"]}
                )
                return cached_entry["dm_channel_id"]
        except Exception as e:
            logger.warning(f"[SlackService] Intermittent failure querying cache ledger: {e}")
            
        # B. API Fallback
        logger.info(f"[SlackService] CACHE MISS: Initiating live DM creation protocol for user={user_id}...")
        dm_res = await self.open_dm_channel(user_id, context)
        dm_channel_id = dm_res["channel_id"]
        
        # C. Commit Mapping to Ledger
        try:
            await cache_coll.update_one(
                {"slack_user_id": user_id},
                {
                    "$set": {
                        "dm_channel_id": dm_channel_id,
                        "display_name": user_data.get("display_name"),
                        "email": user_data.get("email"),
                        "last_updated": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )
            logger.info(f"[SlackService] Successfully synchronized DM routing entry for user={user_id} in persistence ledger.")
        except Exception as e:
            logger.warning(f"[SlackService] Failed persisting DM routing entry to cache ledger: {e}")
            
        return dm_channel_id

    async def send_dm(self, recipient: str, message: str, context: Optional["ToolExecutionContext"] = None) -> Dict[str, Any]:
        """ Orchestrates complete DM dispatch workflow: resolves user, obtains routing channel, and dispatches payload."""
        try:
            # 1. Resolve User Identity
            # If recipient is already an ID starting with U, we skip lookup and build minimal data
            if recipient.startswith("U") and len(recipient) >= 9:
                user_id = recipient
                user_info = {"user_id": user_id, "display_name": recipient, "email": None}
            else:
                user_info = await self.resolve_user(recipient, context)
                if not user_info:
                    raise ValueError(f"Could not resolve Slack user match for identifier: {recipient}")
                user_id = user_info["user_id"]
                
            # 2. Secure DM Routing Gateway
            channel_id = await self.get_or_create_dm_channel(user_id, user_info, context)
            
            # 3. Dispatch Transmission
            logger.info(f"[SlackService] Dispatching secure direct message to resolved channel={channel_id}...")
            client = await self._get_client()
            response = await client.chat_postMessage(
                channel=channel_id,
                text=message
            )
            
            if response.get("ok"):
                logger.info(f"[SlackService] Secure DM posted successfully! TS={response.get('ts')}")
                
                await self._emit_slack_telemetry(
                    TelemetryEventType.SLACK_DM_SENT,
                    context,
                    {"user_id": user_id, "channel_id": channel_id, "ts": response.get("ts")}
                )
                
                return {
                    "success": True,
                    "ts": response.get("ts"),
                    "channel": channel_id,
                    "recipient_user_id": user_id
                }
                
            raise RuntimeError(f"DM execution failure: {response.get('error')}")
        except Exception as e:
            logger.error(f"[SlackService] Real Direct Message execution sequence aborted: {e}")
            raise e


# Centralized instance
slack_service = SlackService()
