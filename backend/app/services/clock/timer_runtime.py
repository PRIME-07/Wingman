import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from backend.app.core.logging import logger
from backend.app.event_bus.bus import event_bus, EventPriority

class TimerRuntime:
    """
    High-fidelity in-memory async scheduler for local temporal tasks.
    Fires persistent events across the central Event Bus upon countdown completions.
    Does not require external brokers, perfect for ephemeral real-time session loops.
    """

    def __init__(self):
        # Tracks currently executing timer task threads: id -> Dict containing task, label, expiration
        self._timers: Dict[str, Dict[str, Any]] = {}

    def create_timer(self, seconds: float, label: str, session_id: Optional[str] = None) -> str:
        """
        Schedules an asynchronous delay worker. 
        Returns unique UUID mapping to track, audit, or cancel countdown states.
        """
        timer_id = str(uuid.uuid4())
        expiry_time = datetime.utcnow() + timedelta(seconds=seconds)

        # Construct async background job routine
        async def _timer_worker():
            try:
                logger.info(f"[TimerRuntime] Staged '{label}' for {seconds}s duration [TimerID={timer_id}].")
                await asyncio.sleep(seconds)
                
                # Time elapsed! Dispatch expired notification to Event Bus
                await self._trigger_expiry(timer_id, label, session_id)
            except asyncio.CancelledError:
                logger.info(f"[TimerRuntime] Timer '{label}' was terminated prematurely.")
            finally:
                # Clean up internal pointer dictionary cleanly
                self._timers.pop(timer_id, None)

        # Initiate running non-blocking task
        task = asyncio.create_task(_timer_worker())
        
        # Track tracking descriptor
        self._timers[timer_id] = {
            "id": timer_id,
            "task": task,
            "label": label,
            "seconds": seconds,
            "expires_at": expiry_time.isoformat(),
            "session_id": session_id
        }
        
        return timer_id

    async def _trigger_expiry(self, timer_id: str, label: str, session_id: Optional[str]):
        """Broadcasting notification across active session sockets."""
        logger.info(f"[TimerRuntime] ALERT: Timer '{label}' expired! Emitting broadcast event.")
        
        # Construct telemetry and user visible notification packet
        alert_payload = {
            "event": "timer_fired",
            "timer_id": timer_id,
            "label": label,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"🚨 Timer Alarm: '{label}' is up!"
        }
        
        # Broadcast as HIGH priority to guarantee swift websocket propagation
        await event_bus.publish(
            topic="telemetry", 
            event_payload=alert_payload, 
            priority=EventPriority.HIGH
        )

    def cancel_timer(self, timer_id: str) -> bool:
        """Cancels active countdown and destroys pointer record."""
        record = self._timers.get(timer_id)
        if not record:
            logger.debug(f"[TimerRuntime] Attemped to cancel non-existent timer={timer_id}.")
            return False
            
        record["task"].cancel()
        # Pop immediately to ensure synchronous lists aren't polluted while the loop cleans up
        self._timers.pop(timer_id, None)
        return True


    def list_active_timers(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Enumerates running timers, optionally scoped to user's active session."""
        active = []
        now = datetime.utcnow()
        for tid, r in self._timers.items():
            # Filter by session if requested
            if session_id and r["session_id"] != session_id:
                continue
                
            # Calculate accurate remainder seconds
            exp = datetime.fromisoformat(r["expires_at"])
            remaining = max(0.0, (exp - now).total_seconds())
            
            active.append({
                "timer_id": tid,
                "label": r["label"],
                "expires_at": r["expires_at"],
                "remaining_seconds": round(remaining, 1),
                "duration_seconds": r["seconds"]
            })
        return active

# Central Instance
timer_runtime = TimerRuntime()
