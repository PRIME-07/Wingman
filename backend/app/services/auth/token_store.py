import json
from datetime import datetime
from typing import Any, Dict, Optional
from backend.app.db.mongodb import mongo_db
from backend.app.core.config import settings
from backend.app.core.logging import logger

class TokenStore:
    """
    Central registry managing persistent runtime tokens and dynamic OAuth access credentials.
    Primary storage utilizes MongoDB to enable multi-tenant scaling, fallbacks yield .env configurations.
    """

    def __init__(self):
        # Staging collection handles
        self._collection_name = "user_credentials"

    async def store_token(self, user_id: str, provider: str, credentials: Dict[str, Any]):
        """
        Saves authorization payloads (access_tokens, refresh_tokens, scopes) securely 
        for a given third-party cloud provider.
        """
        logger.info(f"[TokenStore] Refreshing session storage credentials user='{user_id}' provider='{provider}'...")
        db = mongo_db.get_db()
        coll = db[self._collection_name]
        
        payload = {
            "user_id": user_id,
            "provider": provider.lower(),
            "credentials": credentials, # Secure production vaults should encrypt this block
            "updated_at": datetime.utcnow().isoformat()
        }

        await coll.update_one(
            {"user_id": user_id, "provider": provider.lower()},
            {"$set": payload},
            upsert=True
        )
        logger.info(f"[TokenStore] Credential state persist successful.")

    async def get_token(self, user_id: str, provider: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves dynamically stored token schemas. 
        Returns None if no dynamic token found, allowing service code fallback routines.
        """
        db = mongo_db.get_db()
        coll = db[self._collection_name]
        
        record = await coll.find_one({"user_id": user_id, "provider": provider.lower()})
        if not record:
            return None
            
        return record.get("credentials")

    async def remove_token(self, user_id: str, provider: str):
        """Purges authentication keys (e.g., during user disconnect or logout)."""
        db = mongo_db.get_db()
        coll = db[self._collection_name]
        
        res = await coll.delete_one({"user_id": user_id, "provider": provider.lower()})
        logger.info(f"[TokenStore] Cleaned {res.deleted_count} credential nodes for user='{user_id}'.")

# Central Instance
token_store = TokenStore()
