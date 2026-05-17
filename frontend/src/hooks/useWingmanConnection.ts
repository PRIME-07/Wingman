import { useEffect, useRef, useCallback } from 'react';
import { useChatStore } from '../stores/useChatStore';
import type { HITLRequest } from '../types';


// Production-safe dynamic base URL resolver
const BACKEND_HOST = import.meta.env.VITE_BACKEND_URL || 'localhost:8000';
const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

const CHAT_WS_URL = `${WS_PROTOCOL}//${BACKEND_HOST}/api/v1/chat/ws`;
const TELEMETRY_WS_URL = `${WS_PROTOCOL}//${BACKEND_HOST}/api/v1/telemetry/ws`;

export function useWingmanConnection(threadId: string = 'default-session') {
  const chatWs = useRef<WebSocket | null>(null);
  const telemetryWs = useRef<WebSocket | null>(null);

  const {
    addMessage,
    updateLastMessage,
    setLastMessageContent,
    addTelemetry,
    setHITL,
    setStreaming,
    setWsConnected,
    currentModel,
    currentReasoningEffort,
    isStreaming
  } = useChatStore();

  // Keep-alive and automatic reconnect states
  const reconnectCount = useRef(0);
  const activeThread = useRef(threadId);

  useEffect(() => {
    activeThread.current = threadId;
  }, [threadId]);

  // Keep-alive spatial tracking (cached asynchronously for zero-latency prompt delivery)
  const latestLocation = useRef<{ latitude: number; longitude: number } | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && 'geolocation' in navigator) {
      const updateLocation = (pos: GeolocationPosition) => {
        latestLocation.current = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        };
        console.log('[Geolocation] Runtime state updated:', latestLocation.current);
      };

      const handleError = (err: GeolocationPositionError) => {
        console.warn('[Geolocation] Context permission or update error:', err.message);
      };

      const geoOptions = { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 };

      // 1. Trigger immediate, single-shot resolution for instant readiness
      navigator.geolocation.getCurrentPosition(updateLocation, handleError, geoOptions);

      // 2. Poll geolocation periodically every 15 minutes to respect system resource constraints
      const intervalId = setInterval(() => {
        navigator.geolocation.getCurrentPosition(updateLocation, handleError, geoOptions);
      }, 15 * 60 * 1000);

      return () => clearInterval(intervalId);
    }
  }, []);

  const connect = useCallback(() => {
    console.log('[WS] Initializing bidirectional channels...');

    // Safeguard: Close any existing sockets before recreating to avoid duplicate listeners (e.g. StrictMode)
    if (chatWs.current) {
      chatWs.current.onclose = null;
      chatWs.current.close();
      chatWs.current = null;
    }
    if (telemetryWs.current) {
      telemetryWs.current.onclose = null;
      telemetryWs.current.close();
      telemetryWs.current = null;
    }

    // 1. Estalish Core Chat Loop
    try {
      chatWs.current = new WebSocket(CHAT_WS_URL);

      chatWs.current.onopen = () => {
        console.log('[WS-Chat] Connected successfully.');
        setWsConnected(true);
        reconnectCount.current = 0;
      };

      chatWs.current.onclose = () => {
        console.log('[WS-Chat] Disconnected.');
        setWsConnected(false);
        // Auto-reconnect after backing off
        setTimeout(() => {
          if (reconnectCount.current < 5) {
            reconnectCount.current += 1;
            connect();
          }
        }, 3000);
      };

      chatWs.current.onmessage = (msg) => {
        try {
          const payload = JSON.parse(msg.data);
          console.log('[WS-Chat] Inbound:', payload);

          if (payload.event === 'hitl_suspend') {
            const details = payload.interrupt_details?.[0] || {};
            const hitlReq: HITLRequest = {
              interrupt_id: Math.random().toString(36).substring(2, 9),
              tool: details.tool || 'unknown_tool',
              prompt: details.prompt || 'Approve operation?',
              data: details.data || {}
            };
            setHITL(hitlReq);
            setStreaming(false);
          } else if (payload.event === 'final_response') {
            setStreaming(false);
            // Fallback: overwrite full text to ensure accuracy even if token stream missed chunks
            if (payload.text) {
              setLastMessageContent(payload.text);
            }
            // Clear any pending HITL
            setHITL(null);
          }
        } catch (e) {
          console.error('Failed parsing chat WS message', e);
        }
      };
    } catch (err) {
      console.error('Failed instantiating chat WS', err);
    }

    // 2. Establish Telemetry & Streaming Loop
    try {
      telemetryWs.current = new WebSocket(TELEMETRY_WS_URL);

      telemetryWs.current.onopen = () => {
        console.log('[WS-Telemetry] Connected successfully.');
      };

      telemetryWs.current.onclose = () => {
        console.log('[WS-Telemetry] Disconnected.');
      };

      telemetryWs.current.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data);

          // Extract token streams immediately to assist render performance
          if (event.event_type === 'token_stream') {
            const text = event.payload?.text || event.payload?.token || '';
            updateLastMessage(text);
            return; // Tokens don't clutter advanced telemetry cards
          }

          const rawLabel = event.tool_name || event.node_name || 'System';
          const formattedLabel = event.tool_name
            ? event.tool_name.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ')
            : rawLabel;

          // Map core Backend Telemetry event shapes to UI telemetry state
          addTelemetry({
            type: mapBackendEventType(event.event_type || event.event),
            label: formattedLabel,
            message: generateSummary(event),
            payload: { ...(event.payload || event), backend_type: event.event_type || event.event }
          });

          // Proactive Alerting Logic: Intercept fired timers and calendar hits
          if (event.event === 'timer_fired' || event.event_type === 'timer_fired') {
            console.log('[Telemetry] Timer Fired Event Detected:', event);
            useChatStore.getState().addNotification({
              type: 'timer',
              title: 'Timer Fired',
              message: event.message || `Your timer "${event.label}" has finished.`,
              severity: 'high'
            });
          }

          // Proactive Calendar Refresh Logic: Intercept calendar tool modifications/queries
          if (event.tool_name?.startsWith('calendar_') && (event.event === 'tool_end' || event.event_type === 'tool_end')) {
            console.log('[Telemetry] Calendar Tool execution completed:', event.tool_name);
            window.dispatchEvent(new CustomEvent('refresh-calendar'));
          }

        } catch (e) {
          // Silent catch for parsing non-json heartbeats
        }
      };
    } catch (err) {
      console.error('Failed instantiating telemetry WS', err);
    }

  }, [setWsConnected, setHITL, setStreaming, updateLastMessage, setLastMessageContent, addTelemetry]);

  // Terminate active listeners on cleanups
  useEffect(() => {
    connect();
    return () => {
      chatWs.current?.close();
      telemetryWs.current?.close();
    };
  }, [connect]);

  // Core prompt delivery trigger
  const sendMessage = useCallback((messageText: string, imageBase64?: string) => {
    if (!chatWs.current || chatWs.current.readyState !== WebSocket.OPEN) {
      console.error('WS not active. Cannot push prompt.');
      return;
    }

    // 1. Push UI message
    addMessage('user', messageText);

    // 2. Prepare streaming assistant message
    addMessage('assistant', '');
    setStreaming(true);
    setHITL(null); // clear old

    // 3. Formulate execution packet
    const packet: any = {
      action: 'prompt',
      thread_id: activeThread.current,
      message: messageText,
      priority_tier: currentReasoningEffort.toUpperCase(),
      metadata: {
        model: currentModel,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        client_timestamp: new Date().toISOString(),
        location: latestLocation.current
      }
    };

    if (imageBase64) {
      packet.image = imageBase64;
    }

    chatWs.current.send(JSON.stringify(packet));
  }, [addMessage, setStreaming, setHITL, currentReasoningEffort, currentModel]);

  // HITL decision router
  const respondHITL = useCallback((approved: boolean, reason: string = '') => {
    if (!chatWs.current || chatWs.current.readyState !== WebSocket.OPEN) {
      return;
    }

    setStreaming(true);
    setHITL(null);

    const packet = {
      action: 'resume',
      thread_id: activeThread.current,
      decision: {
        approved,
        reason
      }
    };

    chatWs.current.send(JSON.stringify(packet));
  }, [setStreaming, setHITL]);

  return {
    sendMessage,
    respondHITL,
    isStreaming
  };
}

// Helper Utilities

function mapBackendEventType(bType: string): any {
  switch (bType) {
    case 'graph_started': return 'info';
    case 'node_started': return 'node_entry';
    case 'node_completed': return 'node_exit';
    case 'tool_started': return 'tool_start';
    case 'tool_completed': return 'tool_end';
    case 'tool_failed': return 'error';
    case 'memory_retrieved': return 'retrieval';
    case 'graph_failed': return 'error';
    case 'doc_ingest_progress': return 'info';
    default: return 'info';
  }
}

function generateSummary(event: any): string {
  const { event_type, node_name, tool_name, payload, duration_ms } = event;

  switch (event_type) {
    case 'graph_started':
      return 'Cognitive execution loop initialized.';
    case 'node_started':
      return `Entering computation node '${node_name}'.`;
    case 'node_completed':
      return `Exited node '${node_name}' (Elapsed: ${duration_ms?.toFixed(0) || '?'}ms).`;
    case 'tool_started':
      return `Invoking real-world capability: '${tool_name}'.`;
    case 'tool_completed':
      return `Successfully finalized tool execution '${tool_name}'.`;
    case 'tool_failed':
      return `Tool integration failed: ${payload?.error || 'Unknown interrupt'}`;
    case 'memory_retrieved':
      return `Pulled ${payload?.count || 0} semantic context memories from Neo4j graph.`;
    case 'graph_completed':
      return 'Completed full cognitive traversal path.';
    default:
      return payload?.message || `Event: ${event_type}`;
  }
}
