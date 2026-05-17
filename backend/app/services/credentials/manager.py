import json
import base64
import hashlib
from typing import Any, Dict, Optional
from datetime import datetime
from cryptography.fernet import Fernet
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.memory.mongodb_client import mongo_client

class CredentialManager:
    """
    Handles centralized encrypted token and credential storage in MongoDB.
    Utilizes robust Fernet encryption to guarantee OAuth tokens and sensitive 
    keys are never saved in plain text.
    """
    def __init__(self):
        self._ciphers = {}
        self._active_version = "v1"
        self._initialized = False

    def _derive_fernet(self, raw_key: str) -> Fernet:
        """Derives strong URL-safe 32-byte Fernet-compliant token key from arbitrary inputs."""
        key_digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(key_digest)
        return Fernet(fernet_key)

    def _initialize_cipher(self):
        """Bootstraps primary active cipher and registers rotating fallback decryptors from configuration."""
        if self._initialized:
            return
        
        try:
            # 1. Initialize Primary Active Cipher (v1)
            raw_key = settings.ENCRYPTION_KEY
            if not raw_key or "generate-your-fernet-key-here" in raw_key:
                logger.warning("[CredentialManager] Default or empty ENCRYPTION_KEY detected! Using fallback derivation (UNSAFE FOR PRODUCTION).")
                raw_key = "wingman-fallback-development-key-do-not-use-in-prod"
            
            self._ciphers["v1"] = self._derive_fernet(raw_key)
            
            # 2. Load Rotational Fallbacks
            fallbacks = settings.FALLBACK_ENCRYPTION_KEYS
            if fallbacks:
                parts = [p.strip() for p in fallbacks.split(",") if p.strip()]
                for idx, fb_key in enumerate(parts):
                    v_name = f"v{idx + 2}" # v2, v3...
                    self._ciphers[v_name] = self._derive_fernet(fb_key)
                    logger.info(f"[CredentialManager] Loaded fallback cipher version '{v_name}'.")
            
            self._initialized = True
            logger.info(f"[CredentialManager] Cipher registry loaded successfully with {len(self._ciphers)} version(s).")
        except Exception as e:
            logger.error(f"[CredentialManager] Failed to initialize cipher registry: {e}")
            raise

    def encrypt_data(self, raw_data: Dict[str, Any]) -> str:
        """Encrypts arbitrary dictionary payload using primary 'v1' active key."""
        self._initialize_cipher()
        json_str = json.dumps(raw_data)
        cipher = self._ciphers[self._active_version]
        encrypted_bytes = cipher.encrypt(json_str.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def decrypt_data(self, encrypted_token: str, key_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Decrypts token payloads using specific target key versions, with 
        automated exhaustive attempts against registration fallbacks on error.
        """
        self._initialize_cipher()
        
        # Fast Path: Explicit Version Matching
        if key_version and key_version in self._ciphers:
            try:
                decrypted = self._ciphers[key_version].decrypt(encrypted_token.encode("utf-8"))
                return json.loads(decrypted.decode("utf-8"))
            except Exception:
                logger.warning(f"[CredentialManager] Targeted decryption failed for {key_version}. Falling back to exhaustive try...")
        
        # Exhaustive Path: Attempt all available ciphers
        for v, cipher in self._ciphers.items():
            if v == key_version:
                continue # Skip since it already failed
            try:
                decrypted = cipher.decrypt(encrypted_token.encode("utf-8"))
                return json.loads(decrypted.decode("utf-8"))
            except Exception:
                continue
                
        raise ValueError("Decryption token failure: None of the registered keys could read payload.")

    async def save_credential(self, provider: str, credentials: Dict[str, Any], identity_id: str = "global") -> bool:
        """
        Persists encrypted provider credentials into the central 'credentials' MongoDB collection.
        Partitioned by identity_id to support multi-user isolation.
        """
        try:
            mongo_client.connect()
            coll = mongo_client.db["credentials"]
            
            logger.debug(f"[CredentialManager] Encrypting credentials for provider='{provider}', user='{identity_id}'...")
            encrypted_blob = self.encrypt_data(credentials)
            
            now = datetime.utcnow()
            credential_doc = {
                "provider": provider,
                "identity_id": identity_id,
                "payload": encrypted_blob,
                "key_version": self._active_version,
                "updated_at": now
            }
            
            await coll.update_one(
                {"provider": provider, "identity_id": identity_id},
                {"$set": credential_doc},
                upsert=True
            )
            
            logger.info(f"[CredentialManager] Securely stored credentials for '{provider}' [User={identity_id}].")
            return True
        except Exception as e:
            logger.error(f"[CredentialManager] Failed to save credentials for '{provider}': {e}", exc_info=True)
            return False

    async def get_credential(self, provider: str, identity_id: str = "global") -> Optional[Dict[str, Any]]:
        """Retrieves and decrypts stored credentials for a user identity and provider."""
        try:
            mongo_client.connect()
            coll = mongo_client.db["credentials"]
            
            doc = await coll.find_one({"provider": provider, "identity_id": identity_id})
            
            # Backward compatibility fallback for legacy "global-only" documents
            if not doc and identity_id == "global":
                 doc = await coll.find_one({"provider": provider, "identity_id": {"$exists": False}})
                 
            if not doc:
                logger.debug(f"[CredentialManager] No stored credentials located for '{provider}' [User={identity_id}].")
                return None
            
            encrypted_payload = doc.get("payload")
            if not encrypted_payload:
                logger.warning(f"[CredentialManager] Malformed credential document for '{provider}' - missing payload.")
                return None
            
            # Decrypt with key-version assistance
            key_ver = doc.get("key_version", "v1")
            decrypted_data = self.decrypt_data(encrypted_payload, key_version=key_ver)
            return decrypted_data
        except Exception as e:
            logger.error(f"[CredentialManager] Failed to retrieve/decrypt credentials for '{provider}': {e}", exc_info=True)
            return None

    async def get_secret(self, key_name: str, provider: str = "app_config", identity_id: str = "global") -> Optional[str]:
        """
        Hybrid lookup for secrets.
        1. Checks environment variables (settings) first (.env).
        2. Falls back to MongoDB encrypted storage.
        """
        # 1. Environment Lookup (.env)
        # Map key_name to settings attribute (e.g. 'openai_api_key' -> settings.OPENAI_API_KEY)
        env_val = getattr(settings, key_name.upper(), None)
        
        # Ignore common placeholders
        placeholders = ["your-openai-key", "your-google-maps-api-key", "your-tavily-api-key", "your-openweathermap-key"]
        if env_val and str(env_val).lower() not in placeholders:
            logger.debug(f"[CredentialManager] Secret '{key_name}' resolved from environment.")
            return str(env_val)
            
        # 2. MongoDB Fallback (Encrypted Storage)
        creds = await self.get_credential(provider, identity_id)
        if creds and key_name in creds:
            logger.debug(f"[CredentialManager] Secret '{key_name}' resolved from MongoDB.")
            return creds[key_name]
            
        return None

    async def delete_credential(self, provider: str, identity_id: str = "global") -> bool:
        """Permanently drops credentials for a specific identity and integration provider."""
        try:
            mongo_client.connect()
            coll = mongo_client.db["credentials"]
            
            result = await coll.delete_one({"provider": provider, "identity_id": identity_id})
            if result.deleted_count > 0:
                logger.info(f"[CredentialManager] Purged credentials for provider='{provider}' [User={identity_id}].")
                return True
            else:
                # Fallback cleanup for legacy global
                if identity_id == "global":
                     alt_res = await coll.delete_one({"provider": provider, "identity_id": {"$exists": False}})
                     if alt_res.deleted_count > 0:
                         return True
                logger.debug(f"[CredentialManager] No record found to purge for '{provider}'.")
                return False
        except Exception as e:
            logger.error(f"[CredentialManager] Error deleting credentials for '{provider}': {e}", exc_info=True)
            return False


# Centralized singleton instance
credential_manager = CredentialManager()
