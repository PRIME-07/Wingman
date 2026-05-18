from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from backend.app.services.google.oauth import google_oauth_manager, SCOPES
from backend.app.services.slack.service import slack_service
from backend.app.services.credentials.manager import credential_manager
from backend.app.services.credentials.validator import validator
from backend.app.core.config import settings
from backend.app.core.logging import logger
from cryptography.fernet import Fernet
from typing import Dict, Any

router = APIRouter()

@router.get("/google/connect", summary="Initiate Google OAuth Flow")
async def google_connect():
    """
    Generates a Google Consent URL and redirects the user's agent to authenticate.
    Directly requests long-term offline access tokens.
    """
    try:
        auth_url, _ = await google_oauth_manager.get_authorization_url()
        # Clean user experience redirects user directly to Google
        return RedirectResponse(url=auth_url)
    except ValueError as ve:
        logger.error(f"[AuthAPI] Configuration error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google integration configuration is missing: {str(ve)}"
        )
    except Exception as e:
        logger.error(f"[AuthAPI] Unexpected exception starting OAuth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authentication routing."
        )

@router.get("/google/callback", summary="Handle Google Auth Response")
async def google_callback(
    code: str = Query(None, description="Authorization authorization token"),
    state: str = Query(None, description="Security tracking state"),
    error: str = Query(None, description="Failure indicators returned by provider")
):
    """
    Captures the Redirect callback emitted by Google APIs.
    Exchanges authorization hashes for permanent encrypted API credentials.
    """
    if error:
        logger.error(f"[AuthAPI] Remote callback reported authorization error: {error}")
        return HTMLResponse(
            content=f"""
            <html>
                <body style="font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #0f172a; color: #ef4444;">
                    <div style="text-align: center;">
                        <h1>Authentication Failed</h1>
                        <p>Google returned an error: {error}</p>
                        <button onclick="window.close()" style="padding: 10px 20px; background: #334155; border: none; color: white; border-radius: 5px; cursor: pointer;">Close Window</button>
                    </div>
                </body>
            </html>
            """,
            status_code=status.HTTP_400_BAD_REQUEST
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing active code in redirect handler.")

    # Exchange code with server and encrypt the response payload
    success = await google_oauth_manager.exchange_code_and_save(code=code, state=state)
    
    if success:
        return HTMLResponse(
            content="""
            <html>
                <body style="font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #0f172a; color: #10b981;">
                    <div style="text-align: center; border: 1px solid #1e293b; padding: 40px; border-radius: 10px; background-color: #1e293b;">
                        <h1 style="margin-bottom: 10px;">Integration Successful!</h1>
                        <p style="color: #94a3b8; margin-bottom: 20px;">Wingman now has authorized API control. You may close this tab.</p>
                        <button onclick="window.close()" style="padding: 10px 25px; background: #10b981; border: none; color: white; font-weight: bold; border-radius: 5px; cursor: pointer; transition: all 0.2s;">Done</button>
                    </div>
                </body>
            </html>
            """
        )
    else:
        raise HTTPException(status_code=500, detail="Exchange handshakes failed. Credentials were not authorized.")

@router.get("/google/status", summary="Get Authorization Status")
async def google_status():
    """
    Audits integration status.
    Returns metadata indicating whether a valid, active token persists.
    """
    is_connected = await google_oauth_manager.check_connection_status()
    return {
        "provider": "google",
        "connected": is_connected,
        "scopes_granted": SCOPES if is_connected else []
    }



@router.post("/slack/connect", summary="Save Slack Bot Token")
async def slack_connect(payload: Dict[str, str]):
    """Securely encrypts and persists a user-provided Slack Bot Token."""
    token = payload.get("token")
    # Validate Slack Token
    is_valid = await validator.validate_slack(token)
    if not is_valid:
        await credential_manager.delete_credential("slack")
        raise HTTPException(status_code=400, detail="Slack token verification failed. Please check your token.")
    
    success = await credential_manager.save_credential("slack", {"slack_bot_token": token})
    if success:
        return {"success": True, "message": "Slack token verified and saved."}
    else:
        raise HTTPException(status_code=500, detail="Failed to save Slack token.")

@router.get("/slack/status", summary="Get Slack Authorization Status")
async def slack_status():
    """Checks if Slack bot token is configured and valid."""
    # Hybrid lookup using get_secret
    token = await credential_manager.get_secret("slack_bot_token", provider="slack")
    
    if not token:
        return {
            "provider": "slack",
            "connected": False,
            "config_configured": False
        }
    
    # Actually validate the token
    is_valid = await validator.validate_slack(token)
    
    return {
        "provider": "slack",
        "connected": is_valid,
        "config_configured": True
    }

@router.get("/config/status", summary="Get System Configuration Status")
async def get_config_status():
    """
    Returns the configuration state of all third-party integrations.
    Used by the onboarding UI to show setup guides.
    """
    # 1. Google Config
    google_id = await credential_manager.get_secret("google_client_id", provider="google_config") or \
                await credential_manager.get_secret("google_client_id", provider="google")
    google_secret = await credential_manager.get_secret("google_client_secret", provider="google_config") or \
                    await credential_manager.get_secret("google_client_secret", provider="google")
    
    # 2. Tools Config
    weather_key = await credential_manager.get_secret("weather_api_key", provider="tools")
    tavily_key = await credential_manager.get_secret("tavily_api_key", provider="tools")
    maps_key = await credential_manager.get_secret("google_maps_api_key", provider="tools")
    youtube_key = await credential_manager.get_secret("youtube_api_key", provider="tools")
    
    # 3. Slack Config
    slack_token = await credential_manager.get_secret("slack_bot_token", provider="slack")

    return {
        "google": {
            "configured": bool(google_id and google_secret),
            "has_id": bool(google_id),
            "has_secret": bool(google_secret)
        },
        "tools": {
            "weather": bool(weather_key),
            "search": bool(tavily_key),
            "maps": bool(maps_key),
            "youtube": bool(youtube_key)
        },
        "slack": {
            "configured": bool(slack_token)
        },
        "engine": {
            "openai": bool(
                (await credential_manager.get_secret("openai_api_key", provider="engine")) and 
                (await credential_manager.get_secret("openai_api_key", provider="engine")) != "your-openai-key"
            )
        }
    }

@router.post("/config/save", summary="Save Integration Secret")
async def save_config_secret(payload: Dict[str, Any]):
    """
    Saves an integration secret to MongoDB.
    Expects: { "provider": "google", "secrets": { "google_client_id": "...", "google_client_secret": "..." } }
    """
    provider = payload.get("provider")
    secrets = payload.get("secrets")
    
    if not provider or not secrets:
        raise HTTPException(status_code=400, detail="Missing provider or secrets in payload.")

    # Validation Logic
    is_valid = True
    error_msg = f"Validation failed for {provider} credentials."

    try:
        if provider in ["google", "google_config"]:
            is_valid = await validator.validate_google_oauth(
                secrets.get("google_client_id"), 
                secrets.get("google_client_secret")
            )
        elif provider == "slack":
            is_valid = await validator.validate_slack(secrets.get("slack_bot_token"))
        elif provider == "engine":
            is_valid = await validator.validate_openai(secrets.get("openai_api_key"))
            if not is_valid:
                error_msg = "Invalid OpenAI API Key. Please ensure it starts with 'sk-' and has active credits."
        elif provider == "tools":
            # Validate only the keys present in the payload
            is_valid = True
            if "weather_api_key" in secrets:
                valid_weather = await validator.validate_weather(secrets["weather_api_key"])
                if not valid_weather:
                    is_valid = False
                    error_msg = "Weather API Key validation failed. Please check your key."
            if "tavily_api_key" in secrets:
                valid_tavily = await validator.validate_tavily(secrets["tavily_api_key"])
                if not valid_tavily:
                    is_valid = False
                    error_msg = "Tavily Search Key validation failed. Ensure it starts with 'tvly-'."
            if "google_maps_api_key" in secrets:
                valid_maps = await validator.validate_google_maps(secrets["google_maps_api_key"])
                if not valid_maps:
                    is_valid = False
                    error_msg = "Google Maps Key validation failed or Billing not enabled."
            if "youtube_api_key" in secrets:
                valid_youtube = await validator.validate_youtube(secrets["youtube_api_key"])
                if not valid_youtube:
                    is_valid = False
                    error_msg = "YouTube Data API Key validation failed."

    except Exception as e:
        logger.error(f"Validation exception for {provider}: {e}")
        is_valid = False
        error_msg = f"System error during validation: {str(e)}"

    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
        
    # Merge with existing credentials to be additive
    existing_creds = await credential_manager.get_credential(provider) or {}
    updated_secrets = {**existing_creds, **secrets}
        
    success = await credential_manager.save_credential(provider, updated_secrets)
    if success:
        return {"success": True, "message": f"Configuration for {provider} verified and saved."}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to save configuration for {provider}.")

@router.post("/config/reset", summary="Reset All Persisted Credentials")
async def reset_credentials():
    """
    Clears all saved third-party credentials from MongoDB.
    This enables full re-configuration of all integrations.
    """
    try:
        providers = ["google", "google_config", "slack", "engine", "tools"]
        for provider in providers:
            await credential_manager.delete_credential(provider)
        return {"success": True, "message": "All saved configurations have been reset successfully."}
    except Exception as e:
        logger.error(f"Error resetting credentials: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset credentials: {str(e)}")

@router.get("/generate-encryption-key", summary="Generate a fresh security key")
async def generate_key():
    """Generates a random AES-256 Fernet key for the user to copy into their .env."""
    key = Fernet.generate_key().decode()
    return {
        "key": key,
        "instructions": "Copy this value into your .env as ENCRYPTION_KEY and restart the application."
    }
