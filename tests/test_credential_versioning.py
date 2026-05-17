import pytest
from unittest.mock import patch
from backend.app.services.credentials.manager import CredentialManager
from backend.app.core.config import settings

@pytest.mark.asyncio
async def test_credential_rotational_decryption():
    """
    Validates that the CredentialManager can successfully retrieve and decrypt 
    credentials created under an older key by utilizing configured rotational fallbacks.
    """
    # Use distinct test key and mock mongo or real mongo
    initial_key = "test-rotation-secret-key-alpha-1234"
    rotated_key = "test-rotation-secret-key-bravo-5678"
    
    payload = {"access_token": "pytest-vault-test-token", "refresh_token": "pytest-vault-refresh"}
    
    # Setup test isolation context with localhost Mongo routing
    with patch.object(settings, "ENCRYPTION_KEY", initial_key), \
         patch.object(settings, "FALLBACK_ENCRYPTION_KEYS", ""), \
         patch.object(settings, "MONGODB_URL", "mongodb://localhost:27017/"):
        
        mgr_1 = CredentialManager()
        # Verify initial encryption works
        success = await mgr_1.save_credential(
            provider="pytest_vault_test", 
            credentials=payload, 
            identity_id="pytest_rotation_user"
        )
        assert success is True
        
        # Verify direct decryption reads back correctly
        read_val = await mgr_1.get_credential(
            provider="pytest_vault_test", 
            identity_id="pytest_rotation_user"
        )
        assert read_val == payload

    # NOW SIMULATE ROTATION!
    # settings.ENCRYPTION_KEY is updated to `rotated_key`
    # settings.FALLBACK_ENCRYPTION_KEYS stores `initial_key`
    with patch.object(settings, "ENCRYPTION_KEY", rotated_key), \
         patch.object(settings, "FALLBACK_ENCRYPTION_KEYS", initial_key), \
         patch.object(settings, "MONGODB_URL", "mongodb://localhost:27017/"):
        
        # Reinitialize a fresh manager which loads version-keys
        mgr_rotated = CredentialManager()
        
        # Read back the document encrypted with 'initial_key'
        read_rotated = await mgr_rotated.get_credential(
            provider="pytest_vault_test", 
            identity_id="pytest_rotation_user"
        )
        
        # Ensure fallback logic successfully recovered the token payload!
        assert read_rotated == payload
        print("\n[SUCCESS] Vault rotational decryption verified successfully via fallback logic.")

    # Cleanup after test
    with patch.object(settings, "ENCRYPTION_KEY", rotated_key), \
         patch.object(settings, "FALLBACK_ENCRYPTION_KEYS", initial_key), \
         patch.object(settings, "MONGODB_URL", "mongodb://localhost:27017/"):
         mgr_clean = CredentialManager()
         await mgr_clean.delete_credential(
             provider="pytest_vault_test", 
             identity_id="pytest_rotation_user"
         )
