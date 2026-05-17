import { useEffect } from 'react';
import { useChatStore } from '../../stores/useChatStore';
import { TelemetryEmotionEngine } from '../telemetry-engine';

/**
 * Hook to bridge the ChatStore telemetry stream with the Emotion Engine.
 */
export function useTelemetryEmotion(enabled: boolean = true) {
  const { telemetry } = useChatStore();

  useEffect(() => {
    if (enabled && telemetry.length > 0) {
      const latest = telemetry[0]; // Telemetry is prepended in store (line 162 of useChatStore.ts)
      TelemetryEmotionEngine.processEvent(latest.type, latest.payload || {});
    }
  }, [telemetry, enabled]);
}
