import os
from typing import Any, Dict, Optional, Tuple
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.services.credentials.manager import credential_manager

# Allow insecure HTTP connections for local development OAuth
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Define comprehensive scopes for Wingman's autonomous acts
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

async def get_client_config() -> Dict[str, Any]:
    """Generates dynamic Client configuration by resolving secrets from DB or Environment."""
    client_id = await credential_manager.get_secret("google_client_id", provider="google")
    client_secret = await credential_manager.get_secret("google_client_secret", provider="google")
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    
    if not client_id or not client_secret:
        raise ValueError("Google Client ID or Secret is not configured. Please set them in the UI or .env.")

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": [redirect_uri]
        }
    }

class GoogleOAuthManager:
    """
    Executes Google OAuth initiation, callbacks, and secure automatic token refreshing.
    Tied directly into CredentialManager for secure persistence.
    """
    
    def __init__(self):
        # Map of state -> code_verifier for stateless PKCE validation
        self._active_verifiers = {}

    async def get_authorization_url(self) -> Tuple[str, str]:
        """
        Generates a fully configured OAuth consent URL and its security 'state' token.
        Requests access_type='offline' to guarantee generation of Refresh Tokens.
        """
        config = await get_client_config()
        
        flow = Flow.from_client_config(
            client_config=config,
            scopes=SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
        
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent" # Forces Google to re-send refresh token on consecutive connections
        )
        
        # Record dynamic PKCE verifier for subsequent callback evaluation
        self._active_verifiers[state] = flow.code_verifier
        
        logger.info(f"[GoogleOAuth] Generated state token and consent URI.")
        return auth_url, state

    async def exchange_code_and_save(self, code: str, state: str) -> bool:
        """Exchanges the OAuth callback code for raw tokens and encrypts them securely."""
        try:
            # Recover code verifier associated with the secure tracking state
            code_verifier = self._active_verifiers.pop(state, None)
            
            config = await get_client_config()
            
            flow = Flow.from_client_config(
                client_config=config,
                scopes=SCOPES,
                redirect_uri=settings.GOOGLE_REDIRECT_URI
            )
            
            # Fetch tokens using callback values and PKCE verifier
            flow.fetch_token(code=code, code_verifier=code_verifier)
            credentials = flow.credentials
            
            # Structure raw token dictionary for persistence
            token_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
                "expiry": credentials.expiry.isoformat() if credentials.expiry else None
            }
            
            # Guarantee a refresh token was extracted, otherwise log warning
            if not credentials.refresh_token:
                logger.warning("[GoogleOAuth] SUCCESSFUL AUTH BUT NO REFRESH TOKEN FOUND! Re-authentication will be required frequently unless user revokes permissions and restarts flow.")
            
            await credential_manager.save_credential("google", token_data)
            logger.info("[GoogleOAuth] Exchanged authorization code and encrypted active Google credentials.")
            return True
        except Exception as e:
            logger.error(f"[GoogleOAuth] Failed to complete OAuth code exchange: {e}", exc_info=True)
            return False

    async def get_authenticated_credentials(self) -> Optional[Credentials]:
        """
        Retrieves, deserializes, and validates active Google credentials.
        Performs AUTOMATIC refresh cycles if token expiration thresholds are passed.
        """
        token_data = await credential_manager.get_credential("google")
        if not token_data:
            logger.debug("[GoogleOAuth] No active credentials found in persistent manager.")
            return None
            
        try:
            creds = Credentials.from_authorized_user_info(info=token_data)
            
            # Ensure active token hasn't expired. If so, trigger auto-refresh.
            if creds and creds.expired and creds.refresh_token:
                logger.info("[GoogleOAuth] Credential token expired. Activating auto-refresh protocol...")
                
                # Perform network sync operation inside Request runner
                creds.refresh(Request())
                
                # Re-persist newly minted token
                updated_token_data = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token, # preserved or updated
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes,
                    "expiry": creds.expiry.isoformat() if creds.expiry else None
                }
                await credential_manager.save_credential("google", updated_token_data)
                logger.info("[GoogleOAuth] Auto-refresh successful. Stored new access tokens.")
            
            return creds
        except Exception as e:
            logger.error(f"[GoogleOAuth] CRITICAL ERROR during token evaluation/refresh: {e}", exc_info=True)
            return None

    async def check_connection_status(self) -> bool:
        """Verifies whether valid, active credentials exist and are non-revoked."""
        creds = await self.get_authenticated_credentials()
        return creds is not None and creds.valid

# Singleton runner
google_oauth_manager = GoogleOAuthManager()
