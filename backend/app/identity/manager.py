from typing import Optional, Dict, Any
from datetime import datetime
from backend.app.identity.models import UserIdentityMap, LinkedIdentity
from backend.app.memory.mongodb_client import mongo_client
from backend.app.core.logging import logger

class IdentityAbstractionManager:
    """
    Manages routing mapping rules connecting core Wingman user profiles
    to distinct third-party provider account states in MongoDB.
    """

    async def get_or_create_identity(self, identity_id: str) -> UserIdentityMap:
        """Retrieves a user's full connectivity map, provisioning empty defaults if needed."""
        try:
            mongo_client.connect()
            coll = mongo_client.db["user_identities"]
            
            doc = await coll.find_one({"identity_id": identity_id})
            if doc:
                # Pydantic model loads automatically
                return UserIdentityMap.model_validate(doc)
                
            # Provision default record
            new_profile = UserIdentityMap(identity_id=identity_id)
            await coll.insert_one(new_profile.model_dump())
            logger.info(f"[IdentityManager] Provisioned fresh user mapping container for ID={identity_id}")
            return new_profile
            
        except Exception as e:
            logger.error(f"[IdentityManager] Failed resolving profile container: {e}")
            return UserIdentityMap(identity_id=identity_id)

    async def link_provider_identity(
        self, 
        identity_id: str, 
        provider: str, 
        linked_data: Dict[str, Any]
    ) -> bool:
        """Appends or overwrites a connected account map entry for a user."""
        try:
            profile = await self.get_or_create_identity(identity_id)
            
            linked = LinkedIdentity(
                provider=provider,
                email=linked_data.get("email"),
                user_id=linked_data.get("user_id"),
                scopes=linked_data.get("scopes", []),
                active=True
            )
            
            profile.identities[provider] = linked
            profile.updated_at = datetime.utcnow()
            
            mongo_client.connect()
            await mongo_client.db["user_identities"].replace_one(
                {"identity_id": identity_id},
                profile.model_dump()
            )
            logger.info(f"[IdentityManager] Successfully linked '{provider}' to user='{identity_id}'.")
            return True
        except Exception as e:
            logger.error(f"[IdentityManager] Failed linking provider mapping: {e}")
            return False

    async def is_provider_active(self, identity_id: str, provider: str) -> bool:
        """Utility to instantly confirm if a tool can schedule a real request for this profile."""
        profile = await self.get_or_create_identity(identity_id)
        linked = profile.identities.get(provider)
        return linked.active if linked else False

# Single pointer for identity coordination
identity_manager = IdentityAbstractionManager()
