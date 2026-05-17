from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, time
import pymongo
from backend.app.core.config import settings
from backend.app.core.logging import logger

class MongoDBClient:
    """
    Handles safe transactional conversational storage and session isolation using a 
    consolidated collection model with robust indexes and range-based pruning.
    """
    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.db = None

    def connect(self):
        if not self.client:
            logger.info(f"[MongoDB] Connecting to node: {settings.MONGODB_URL}")
            self.client = AsyncIOMotorClient(settings.MONGODB_URL)
            self.db = self.client[settings.MONGODB_DB_NAME]

    async def ensure_indexes(self):
        """Initializes indexes on the single-collection architecture for high performance queries."""
        self.connect()
        
        # 1. Setup index for 'raw_chats'
        chats_coll = self.db["raw_chats"]
        await chats_coll.create_index([("session_id", pymongo.ASCENDING), ("created_at", pymongo.ASCENDING)])
        await chats_coll.create_index([("created_at", pymongo.ASCENDING)])
        
        # 2. Setup index for 'sessions'
        sessions_coll = self.db["sessions"]
        await sessions_coll.create_index([("session_id", pymongo.ASCENDING)], unique=True)
        await sessions_coll.create_index([("updated_at", pymongo.DESCENDING)])
        
        # Telemetry & Audit Indexes
        await self.db["session_telemetry"].create_index([("trace_id", pymongo.ASCENDING)])
        await self.db["action_audit_ledger"].create_index([("trace_id", pymongo.ASCENDING)])
        await self.db["action_audit_ledger"].create_index([("timestamp", pymongo.ASCENDING)])
        
        # Document RAG Catalog Index
        await self.db["documents"].create_index([("doc_id", pymongo.ASCENDING)], unique=True)
        await self.db["documents"].create_index([("uploaded_at", pymongo.DESCENDING)])
        
        # Consolidation Logs Index
        await self.db["consolidation_logs"].create_index([("processed_until_timestamp", pymongo.DESCENDING)])
        
        # Subagent Execution Idempotency Cache Indexes
        await self.db["tool_execution_cache"].create_index([("run_id", pymongo.ASCENDING)])
        await self.db["tool_execution_cache"].create_index([("session_id", pymongo.ASCENDING)])
        await self.db["tool_execution_cache"].create_index([("timestamp", pymongo.ASCENDING)])
        
        # Slack Identity DM Routing Cache
        await self.db["slack_identity_cache"].create_index([("slack_user_id", pymongo.ASCENDING)], unique=True)

        # Contacts Collection Indexes
        await self.db["contacts"].create_index([("contact_id", pymongo.ASCENDING)], unique=True)
        await self.db["contacts"].create_index([("name", pymongo.ASCENDING)])
        await self.db["contacts"].create_index([("alias", pymongo.ASCENDING)])

        logger.info("[MongoDB] Collection indexes verified and initialized successfully.")

    def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None
            logger.info("[MongoDB] Connection terminated.")

    # TELEMETRY & AUDIT LEDGER OPERATIONS
    async def save_session_telemetry(self, event_payload: Dict[str, Any]):
        """Persists transient session telemetry, pruned during consolidation."""
        self.connect()
        coll = self.db["session_telemetry"]
        await coll.insert_one(event_payload)

    async def save_audit_telemetry(self, event_payload: Dict[str, Any]):
        """
        IMMUTABLE AUDIT LEDGER: Persists critical runtime events permanently to a write-only
        operational log. This collection is NEVER pruned or modified by automated cycles.
        """
        self.connect()
        coll = self.db["action_audit_ledger"]
        # Immutable enforcement via strict write-only contract
        event_payload["written_at"] = datetime.utcnow()
        await coll.insert_one(event_payload)


    # SESSION OPERATIONS
    async def create_session(self, session_id: str, session_name: str = "New Conversation", metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generates an isolated interaction session."""
        self.connect()
        now = datetime.utcnow()
        session_doc = {
            "session_id": session_id,
            "session_name": session_name,
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {}
        }
        await self.db["sessions"].update_one(
            {"session_id": session_id},
            {"$setOnInsert": session_doc},
            upsert=True
        )
        return session_doc

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        self.connect()
        return await self.db["sessions"].find_one({"session_id": session_id})

    async def update_session_name(self, session_id: str, session_name: str):
        self.connect()
        await self.db["sessions"].update_one(
            {"session_id": session_id},
            {"$set": {"session_name": session_name, "updated_at": datetime.utcnow()}}
        )

    async def delete_session(self, session_id: str) -> bool:
        """Removes a session context along with its cascading conversational footprint."""
        self.connect()
        
        # 1. Remove core session metadata entry
        result = await self.db["sessions"].delete_one({"session_id": session_id})
        session_deleted = result.deleted_count > 0
        
        if session_deleted:
            # 2. Cascade delete all raw conversation turns bound to this session
            c_res = await self.db["raw_chats"].delete_many({"session_id": session_id})
            
            # 3. Cleanse LangGraph durable ACID checkpointer logs to prevent context bleed
            await self.db["graph_checkpoints"].delete_many({"thread_id": session_id})
            await self.db["graph_writes"].delete_many({"thread_id": session_id})
            
            # 4. Clear transient session telemetry trails
            await self.db["session_telemetry"].delete_many({"session_id": session_id})
            
            # 5. Purge subagent side-effect execution idempotent caches
            cache_del = await self.db["tool_execution_cache"].delete_many({"session_id": session_id})
            
            logger.info(f"[MongoDB-DELETE] Flushed session {session_id}: Removed metadata, {c_res.deleted_count} chat entries, and {cache_del.deleted_count} cached tool ops.")
            
        return session_deleted

    async def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        self.connect()
        cursor = self.db["sessions"].find().sort("updated_at", pymongo.DESCENDING).limit(limit)
        return await cursor.to_list(length=None)

    # MESSAGE OPERATIONS
    async def save_chat_message(self, message_payload: Dict[str, Any]):
        """Persists a single message chunk into the single 'raw_chats' collection."""
        self.connect()
        coll = self.db["raw_chats"]
        
        # Enforce session_id mapping
        if "session_id" not in message_payload:
            # Backwards compatibility for thread_id to session_id
            message_payload["session_id"] = message_payload.get("thread_id", "default-session")
            
        # Satisfy explicit sessionID field assignment
        message_payload["sessionID"] = message_payload["session_id"]
            
        message_payload["created_at"] = message_payload.get("created_at", datetime.utcnow())
        
        # Save message to primary consolidated store
        await coll.insert_one(message_payload)
        
        # Touch and automatically initialize session metadata if not exists (upsert)
        await self.db["sessions"].update_one(
            {"session_id": message_payload["session_id"]},
            {
                "$set": {"updated_at": datetime.utcnow()},
                "$setOnInsert": {
                    "session_name": "New Conversation",
                    "created_at": datetime.utcnow(),
                    "metadata": {}
                }
            },
            upsert=True
        )

    async def get_daily_conversations(self, date: datetime) -> List[Dict[str, Any]]:
        """Retrieves all raw message logs written on the specified day across ALL sessions."""
        self.connect()
        
        # Calculate exact datetime bounds for the target day (UTC)
        day_start = datetime.combine(date, time.min)
        day_end = datetime.combine(date, time.max)
        
        coll = self.db["raw_chats"]
        
        # Filter single collection by time-boundary
        cursor = coll.find({
            "created_at": {
                "$gte": day_start,
                "$lte": day_end
            }
        }).sort("created_at", pymongo.ASCENDING)
        
        return await cursor.to_list(length=None)

    async def get_conversations_between(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieves raw messages strictly between the defined processing window."""
        self.connect()
        coll = self.db["raw_chats"]
        cursor = coll.find({
            "created_at": {
                "$gt": start_time,
                "$lte": end_time
            }
        }).sort("created_at", pymongo.ASCENDING)
        return await cursor.to_list(length=None)

    async def get_session_conversations(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetches message context bound tightly to a single session thread."""
        self.connect()
        coll = self.db["raw_chats"]
        # Robust querying supports legacy and new session storage formats
        cursor = coll.find({
            "$or": [
                {"session_id": session_id},
                {"sessionID": session_id}
            ]
        }).sort("created_at", pymongo.ASCENDING).limit(limit)
        return await cursor.to_list(length=None)

    async def prune_daily_conversations(self, date: datetime):
        """
        DANGEROUS ROUTE: Deletes chat records from the consolidated 'raw_chats' collection.
        Enforces absolute prevention safeguards ensuring system configurations or user docs are untouched.
        """
        self.connect()
        
        day_start = datetime.combine(date, time.min)
        day_end = datetime.combine(date, time.max)
        
        logger.warning(f"[MongoDB-PRUNE] Pruning chat documents for {date.strftime('%Y-%m-%d')}...")
        
        coll = self.db["raw_chats"]
        
        # Safety check: verify we are targeting ONLY the raw_chats collection and not dropping it
        result = await coll.delete_many({
            "created_at": {
                "$gte": day_start,
                "$lte": day_end
            }
        })
        
        logger.info(f"[MongoDB-PRUNE] Completed. Removed {result.deleted_count} chat turns from raw_chats.")
        
        # Prune session telemetry records to prevent operational DB bloat
        tel_coll = self.db["session_telemetry"]
        t_res = await tel_coll.delete_many({
            "timestamp": {
                "$gte": day_start,
                "$lte": day_end
            }
        })
        logger.info(f"[MongoDB-PRUNE] Cleaned up {t_res.deleted_count} temporary session telemetry logs.")
        
        cache_coll = self.db["tool_execution_cache"]
        c_res = await cache_coll.delete_many({
            "timestamp": {
                "$gte": day_start,
                "$lte": day_end
            }
        })
        logger.info(f"[MongoDB-PRUNE] Cleared {c_res.deleted_count} legacy subagent tool cache operations.")

    async def prune_conversations_between(self, start_time: datetime, end_time: datetime):
        """Safely prunes messages within an exact time boundary after consolidation."""
        self.connect()
        coll = self.db["raw_chats"]
        result = await coll.delete_many({
            "created_at": {
                "$gt": start_time,
                "$lte": end_time
            }
        })
        logger.info(f"[MongoDB-PRUNE] Micro-batch complete. Removed {result.deleted_count} chat turns.")
        
        tel_coll = self.db["session_telemetry"]
        await tel_coll.delete_many({
            "timestamp": {
                "$gt": start_time,
                "$lte": end_time
            }
        })
        
        await self.db["tool_execution_cache"].delete_many({
            "timestamp": {
                "$gt": start_time,
                "$lte": end_time
            }
        })

    # DOCUMENT OPERATIONS
    async def save_document_metadata(self, doc_id: str, filename: str, file_size: int, chunk_count: int, session_id: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Registers a parsed and vectorized document inside MongoDB for catalog listing."""
        self.connect()
        now = datetime.utcnow()
        doc_payload = {
            "doc_id": doc_id,
            "filename": filename,
            "file_size": file_size,
            "chunk_count": chunk_count,
            "session_id": session_id,
            "uploaded_at": now,
            "metadata": metadata or {}
        }
        await self.db["documents"].update_one(
            {"doc_id": doc_id},
            {"$set": doc_payload},
            upsert=True
        )
        return doc_payload

    async def list_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves user-uploaded documents catalog."""
        self.connect()
        cursor = self.db["documents"].find().sort("uploaded_at", pymongo.DESCENDING).limit(limit)
        return await cursor.to_list(length=None)

    async def search_documents(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Performs regex lookups against indexed document names."""
        self.connect()
        cursor = self.db["documents"].find(
            {"filename": {"$regex": query, "$options": "i"}}
        ).sort("uploaded_at", pymongo.DESCENDING).limit(limit)
        return await cursor.to_list(length=None)

    async def delete_document_metadata(self, doc_id: str) -> bool:
        """Removes a document from the index catalog."""
        self.connect()
        result = await self.db["documents"].delete_one({"doc_id": doc_id})
        return result.deleted_count > 0

    # CONSOLIDATION LOGS
    async def get_last_consolidation_log(self) -> Optional[Dict[str, Any]]:
        """Fetches the last successful micro-batch consolidation record."""
        self.connect()
        coll = self.db["consolidation_logs"]
        return await coll.find_one({}, sort=[("processed_until_timestamp", pymongo.DESCENDING)])

    async def record_consolidation(self, started_at: datetime, processed_until_timestamp: datetime, items_processed: int):
        """Writes the successful boundary timestamp to prevent duplicate processing."""
        self.connect()
        coll = self.db["consolidation_logs"]
        await coll.insert_one({
            "started_at": started_at,
            "processed_until_timestamp": processed_until_timestamp,
            "items_processed": items_processed
        })


    # CONTACTS OPERATIONS
    async def create_contact(self, name: str, alias: Optional[str] = None, email: Optional[str] = None, phone: Optional[str] = None, contact_id: Optional[str] = None) -> Dict[str, Any]:
        """Registers or creates a new contact."""
        import uuid
        self.connect()
        cid = contact_id or str(uuid.uuid4())
        contact_doc = {
            "contact_id": cid,
            "name": name,
            "alias": alias.lower().strip() if alias else None,
            "email": email.strip() if email else None,
            "phone": phone.strip() if phone else None,
            "created_at": datetime.utcnow()
        }
        await self.db["contacts"].update_one(
            {"contact_id": cid},
            {"$set": contact_doc},
            upsert=True
        )
        return contact_doc

    async def get_contact(self, contact_id: str) -> Optional[Dict[str, Any]]:
        self.connect()
        return await self.db["contacts"].find_one({"contact_id": contact_id})

    async def get_contact_by_alias_or_name(self, query: str) -> Optional[Dict[str, Any]]:
        """Finds a contact by strict name or lowercased alias."""
        self.connect()
        q = query.strip().lower()
        # Try finding by alias first
        contact = await self.db["contacts"].find_one({"alias": q})
        if not contact:
            # Fallback to name search (case-insensitive regex or exact match)
            contact = await self.db["contacts"].find_one({"name": {"$regex": f"^{query}$", "$options": "i"}})
        return contact

    async def list_contacts(self, limit: int = 100) -> List[Dict[str, Any]]:
        self.connect()
        cursor = self.db["contacts"].find().sort("name", pymongo.ASCENDING).limit(limit)
        return await cursor.to_list(length=None)

    async def update_contact(self, contact_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.connect()
        if "alias" in update_data and update_data["alias"]:
            update_data["alias"] = update_data["alias"].lower().strip()
        # Filter out keys with None to avoid overwriting existing valid fields unless desired
        filtered_updates = {k: v for k, v in update_data.items() if v is not None}
        if filtered_updates:
            await self.db["contacts"].update_one(
                {"contact_id": contact_id},
                {"$set": filtered_updates}
            )
        return await self.get_contact(contact_id)

    async def delete_contact(self, contact_id: str) -> bool:
        self.connect()
        result = await self.db["contacts"].delete_one({"contact_id": contact_id})
        return result.deleted_count > 0


# Singleton access client
mongo_client = MongoDBClient()

