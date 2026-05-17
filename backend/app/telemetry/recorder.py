from backend.app.telemetry.schemas import TelemetryEvent, TelemetryDurabilityTier
from backend.app.memory.mongodb_client import mongo_client
from backend.app.core.logging import logger

class TelemetryStorageRecorder:
    """
    Asynchronous subscriber hook for the telemetry bus channel.
    Examines retention tiers and routes records into appropriate persistent stores.
    """
    
    async def record_event(self, event: TelemetryEvent):
        """Consumes emitted telemetry models and enforces durability boundaries."""
        try:
            durability = getattr(event, "durability", TelemetryDurabilityTier.TRANSIENT)
            
            # Durability Tier Logic:
            # 1. TRANSIENT: Never save (e.g. Streaming chunk events, Heartbeats)
            if durability == TelemetryDurabilityTier.TRANSIENT:
                return
                
            # Serialize schema to dict format for raw Mongo insertions
            payload = event.model_dump()
            
            # 2. SESSION: Save to isolated session telemetry store (Pruned daily)
            if durability == TelemetryDurabilityTier.SESSION:
                await mongo_client.save_session_telemetry(payload)
                
            # 3. DURABLE / PERMANENT: Save into permanent Immutable Action Audit Ledger
            elif durability in [TelemetryDurabilityTier.DURABLE, TelemetryDurabilityTier.PERMANENT]:
                await mongo_client.save_audit_telemetry(payload)
                
        except Exception as e:
            logger.error(f"[Telemetry-Recorder] Failed writing telemetry (Tier={event.durability}): {e}")

# Singleton access
telemetry_recorder = TelemetryStorageRecorder()
