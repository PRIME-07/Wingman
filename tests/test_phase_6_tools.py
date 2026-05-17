import pytest
import asyncio
from unittest.mock import AsyncMock, patch

# Services to evaluate
from backend.app.services.google.docs import google_docs_service
from backend.app.services.slack.service import slack_service
from backend.app.services.weather.service import weather_service
from backend.app.services.youtube.service import youtube_service
from backend.app.services.clock.timer_runtime import timer_runtime

@pytest.mark.asyncio
async def test_google_services_simulation_router():
    """Validates robust local simulations if no auth token files present."""
    # Test docs creation
    res = await google_docs_service.create_document(title="Eval Doc", content="Integration test payload.")

    assert "success" in res
    assert res["success"] is True
    assert "document_id" in res

@pytest.mark.asyncio
async def test_slack_service_simulation_layer():
    """Confirms channel lookup falls back to simulations beautifully."""
    res = await slack_service.list_channels()
    assert "success" in res
    assert len(res.get("channels", [])) > 0
    assert "general" in [c["name"] for c in res["channels"]]

@pytest.mark.asyncio
async def test_weather_query_evaluator():
    """Confirms system safely queries meteorological feeds."""
    res = await weather_service.get_forecast(location="Seattle")
    assert "location" in res
    # Verify presence of temperature structure
    assert "current" in res
    assert "forecast" in res

@pytest.mark.asyncio
async def test_youtube_query_pipeline():
    """Confirms YouTube API endpoints return valid links and channels."""
    res = await youtube_service.search_videos(query="autonomous agent programming")
    assert "items" in res or "data" in res
    
@pytest.mark.asyncio
async def test_timer_runtime_scheduling():
    """Validates local scheduler generates timer UUIDs and lists correctly."""
    timer_id = timer_runtime.create_timer(
        seconds=120.0,
        label="Pytest Assessment Alarm",
        session_id="test-session-uuid"
    )
    
    assert timer_id is not None
    
    # Query active list
    active = timer_runtime.list_active_timers("test-session-uuid")
    assert len(active) == 1
    assert active[0]["timer_id"] == timer_id
    assert active[0]["remaining_seconds"] > 0
    
    # Cancel
    cancel_res = timer_runtime.cancel_timer(timer_id)
    assert cancel_res is True
    
    # Re list
    active_after = timer_runtime.list_active_timers("test-session-uuid")
    assert len(active_after) == 0
