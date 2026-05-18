import { create } from 'zustand';
import type { Message, TelemetryEvent, HITLRequest, ModelTier, ReasoningEffort } from '../types';


interface ChatState {
  messages: Message[];
  telemetry: TelemetryEvent[];
  activeHITL: HITLRequest | null;
  isStreaming: boolean;
  wsConnected: boolean;
  currentModel: ModelTier;
  currentReasoningEffort: ReasoningEffort;
  theme: 'dark' | 'light';
  isTelemetryOpen: boolean;
  isLoadingHistory: boolean;
  currentSessionId: string;
  activeSidebarTab: 'chat' | 'vault' | 'search' | 'folder' | 'integrations' | 'contacts' | 'timers' | null;
  googleConnected: boolean | null;
  slackConnected: boolean | null;
  configStatus: {
    google: { configured: boolean, has_id: boolean, has_secret: boolean },
    tools: { weather: boolean, search: boolean, maps: boolean, youtube: boolean },
    memory: { pinecone: boolean, neo4j: boolean, pinecone_env: boolean, aura_info: boolean },
    slack: { configured: boolean },
    engine: { openai: boolean }
  } | null;
  isAuthPromptOpen: boolean;
  isRightSidebarOpen: boolean;
  activeTimers: any[];
  upcomingEvents: any[];
  reminders: any[];
  notifications: any[];
  
  // Actions
  addNotification: (notification: any) => void;
  removeNotification: (id: string) => void;
  setAuthPromptOpen: (open: boolean) => void;
  setRightSidebarOpen: (open: boolean) => void;
  setActiveTimers: (timers: any[]) => void;
  setUpcomingEvents: (events: any[]) => void;
  setReminders: (reminders: any[]) => void;
  setActiveSidebarTab: (tab: 'chat' | 'vault' | 'search' | 'folder' | 'integrations' | 'contacts' | 'timers' | null) => void;
  addMessage: (role: 'user' | 'assistant' | 'system', content: string) => string;
  updateLastMessage: (content: string) => void;
  setLastMessageContent: (content: string) => void;
  clearMessages: () => void;
  
  addTelemetry: (event: Omit<TelemetryEvent, 'id' | 'timestamp'>) => void;
  clearTelemetry: () => void;
  
  setHITL: (hitl: HITLRequest | null) => void;
  setStreaming: (streaming: boolean) => void;
  setWsConnected: (connected: boolean) => void;
  
  setModel: (model: ModelTier) => void;
  setReasoningEffort: (effort: ReasoningEffort) => void;
  
  toggleTheme: () => void;
  setTheme: (theme: 'dark' | 'light') => void;
  
  toggleTelemetry: () => void;
  setCurrentSessionId: (id: string) => void;
  setMessages: (messages: Message[]) => void;
  fetchHistory: (sessionId: string) => Promise<void>;
  checkGoogleStatus: () => Promise<void>;
  checkSlackStatus: () => Promise<void>;
  fetchConfigStatus: () => Promise<void>;
  saveSecret: (provider: string, secrets: Record<string, string>) => Promise<{ success: boolean; message?: string }>;
  resetConfig: () => Promise<{ success: boolean; message?: string }>;
}

const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  if (import.meta.env.VITE_API_BASE_URL) return import.meta.env.VITE_API_BASE_URL;
  const BACKEND_HOST = import.meta.env.VITE_BACKEND_URL || 'localhost:8000';
  const HTTP_PROTOCOL = window.location.protocol === 'https:' ? 'https:' : 'http:';
  return `${HTTP_PROTOCOL}//${BACKEND_HOST}/api/v1`;
};

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  telemetry: [],
  activeHITL: null,
  isStreaming: false,
  wsConnected: false,
  currentModel: 'GPT-5.4-mini',
  currentReasoningEffort: 'Low',
  theme: (localStorage.getItem('wingman-theme') as 'dark' | 'light') || 'dark',
  isTelemetryOpen: true,
  isLoadingHistory: true,
  currentSessionId: (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15),
  activeSidebarTab: 'chat',
  googleConnected: null,
  slackConnected: null,
  configStatus: null,
  isAuthPromptOpen: false,
  isRightSidebarOpen: true,
  activeTimers: [],
  upcomingEvents: [],
  reminders: [],
  notifications: [],

  addNotification: (n) => set((state) => ({ 
    notifications: [...state.notifications, { ...n, id: n.id || Math.random().toString(36).substr(2, 9), timestamp: new Date() }] 
  })),
  removeNotification: (id) => set((state) => ({ 
    notifications: state.notifications.filter(n => n.id !== id) 
  })),

  setAuthPromptOpen: (open) => set({ isAuthPromptOpen: open }),
  setRightSidebarOpen: (open) => set({ isRightSidebarOpen: open }),
  setActiveTimers: (timers) => set({ activeTimers: timers }),
  setUpcomingEvents: (events) => set({ upcomingEvents: events }),
  setReminders: (reminders) => set({ reminders: reminders }),
  setActiveSidebarTab: (tab) => set({ activeSidebarTab: tab }),

  addMessage: (role, content) => {
    const id = Math.random().toString(36).substring(2, 15);
    const newMessage: Message = {
      id,
      role,
      content,
      timestamp: new Date().toISOString(),
    };
    set((state) => ({ messages: [...state.messages, newMessage] }));
    return id;
  },

  updateLastMessage: (content) => {
    set((state) => {
      if (state.messages.length === 0) return state;
      const updated = [...state.messages];
      const lastIndex = updated.length - 1;
      const last = { ...updated[lastIndex] };
      if (last.role === 'assistant') {
        last.content += content;
        updated[lastIndex] = last;
        return { messages: updated };
      }
      return state;
    });
  },

  setLastMessageContent: (content) => {
    set((state) => {
      if (state.messages.length === 0) return state;
      const updated = [...state.messages];
      const lastIndex = updated.length - 1;
      const last = { ...updated[lastIndex] };
      if (last.role === 'assistant') {
        last.content = content;
        updated[lastIndex] = last;
        return { messages: updated };
      }
      return state;
    });
  },

  clearMessages: () => set({ messages: [], activeHITL: null, isLoadingHistory: false }),

  addTelemetry: (event) => {
    const newEvent: TelemetryEvent = {
      ...event,
      id: Math.random().toString(36).substring(2, 15),
      timestamp: new Date().toISOString(),
    };
    set((state) => ({ telemetry: [newEvent, ...state.telemetry].slice(0, 150) })); // Cap at 150 items
  },

  clearTelemetry: () => set({ telemetry: [] }),

  setHITL: (hitl) => set({ activeHITL: hitl }),
  
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  
  setWsConnected: (connected) => set({ wsConnected: connected }),

  setModel: (model) => set({ currentModel: model }),
  
  setReasoningEffort: (effort) => set({ currentReasoningEffort: effort }),

  toggleTheme: () => {
    const newTheme = get().theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('wingman-theme', newTheme);
    // Apply side-effect to HTML root
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    set({ theme: newTheme });
  },

  setTheme: (theme) => {
    localStorage.setItem('wingman-theme', theme);
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    set({ theme });
  },

  toggleTelemetry: () => set((state) => ({ isTelemetryOpen: !state.isTelemetryOpen })),
  
  setCurrentSessionId: (id) => {
    const current = get().currentSessionId;
    const hasMessages = get().messages.length > 0;
    
    // Avoid clearing state if we are already in this session and have data
    if (current === id && hasMessages) return;
    
    set({ currentSessionId: id, messages: [], activeHITL: null, isStreaming: false, isLoadingHistory: !!id });
    
    // Auto-trigger hydration if we have a valid ID
    if (id) {
      get().fetchHistory(id);
    }
  },
  
  setMessages: (messages) => set({ messages }),

  fetchHistory: async (sessionId) => {
    if (!sessionId) {
      set({ isLoadingHistory: false });
      return;
    }
    set({ isLoadingHistory: true });
    try {
      const API_BASE_URL = getApiBaseUrl();
      const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`);
      if (res.ok) {
        const data = await res.json();
        const mapped: Message[] = data.map((m: any) => ({
          id: m.trace_id || Math.random().toString(36).substring(2, 15),
          role: m.role,
          content: m.content,
          timestamp: m.created_at
        }));
        set({ messages: mapped });
      }
    } catch (err) {
      console.error("[ChatStore] Failed fetching session messages:", err);
    } finally {
      set({ isLoadingHistory: false });
    }
  },

  checkGoogleStatus: async () => {
    try {
      const API_BASE_URL = getApiBaseUrl();
      const res = await fetch(`${API_BASE_URL}/auth/google/status`);
      if (res.ok) {
        const data = await res.json();
        set({ googleConnected: data.connected });
      }
    } catch (err) {
      console.error("[ChatStore] Google status check failed:", err);
    }
  },

  checkSlackStatus: async () => {
    try {
      const API_BASE_URL = getApiBaseUrl();
      const res = await fetch(`${API_BASE_URL}/auth/slack/status`);
      if (res.ok) {
        const data = await res.json();
        // data.connected means token is working, data.config_configured means token is in storage/env
        set({ slackConnected: data.connected });
      }
    } catch (err) {
      console.error("[ChatStore] Slack status check failed:", err);
    }
  },

  fetchConfigStatus: async () => {
    try {
      const API_BASE_URL = getApiBaseUrl();
      const res = await fetch(`${API_BASE_URL}/auth/config/status`);
      if (res.ok) {
        const data = await res.json();
        set({ configStatus: data });
      }
    } catch (err) {
      console.error("[ChatStore] Config status fetch failed:", err);
    }
  },

  saveSecret: async (provider, secrets) => {
    try {
      const API_BASE_URL = getApiBaseUrl();
      const res = await fetch(`${API_BASE_URL}/auth/config/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, secrets })
      });
      
      const data = await res.json();
      
      if (res.ok) {
        await get().fetchConfigStatus();
        return { success: true };
      }
      return { success: false, message: data.detail || 'Validation failed' };
    } catch (err) {
      console.error(`[ChatStore] Failed to save secret for ${provider}:`, err);
      return { success: false, message: 'Network error or system failure' };
    }
  },

  resetConfig: async () => {
    try {
      const API_BASE_URL = getApiBaseUrl();
      const res = await fetch(`${API_BASE_URL}/auth/config/reset`, {
        method: 'POST',
      });
      const data = await res.json();
      if (res.ok) {
        await get().fetchConfigStatus();
        await get().checkGoogleStatus();
        await get().checkSlackStatus();
        return { success: true, message: data.message };
      }
      return { success: false, message: data.detail || 'Reset failed' };
    } catch (err) {
      console.error("[ChatStore] Reset configurations failed:", err);
      return { success: false, message: 'Network error or system failure' };
    }
  },
}));
