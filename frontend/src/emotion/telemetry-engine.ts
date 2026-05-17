import type { WingmanEmotion } from './emotion-map';
import { emotionEngine } from './engine';

/**
 * Maps incoming telemetry events to emotional shifts.
 */
export const TelemetryEmotionEngine = {
  processEvent(eventType: string, payload: any) {
    // 1. Explicit emotion signals from backend
    if (payload?.emotion) {
      emotionEngine.transition(payload.emotion as WingmanEmotion, true);
      return;
    }

    // 2. Implicit mapping based on event types
    switch (eventType) {
      case 'graph_started':
        emotionEngine.transition('happy');
        break;
      
      case 'llm_started':
      case 'node_started':
        emotionEngine.transition('thinking');
        break;
        
      case 'memory_retrieved':
        emotionEngine.transition('recollecting');
        break;
        
      case 'tool_started':
        emotionEngine.transition('excited');
        break;
        
      case 'tool_failed':
        emotionEngine.transition('worried');
        break;
        
      case 'graph_completed':
        emotionEngine.transition('proud');
        break;
        
      case 'graph_failed':
        emotionEngine.transition('sad');
        break;
        
      case 'hitl_requested':
        emotionEngine.transition('confused');
        break;
    }
  }
};
