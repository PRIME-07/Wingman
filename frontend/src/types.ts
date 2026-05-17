export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

export interface TelemetryEvent {
  id: string;
  timestamp: string;
  type: 'node_entry' | 'node_exit' | 'tool_start' | 'tool_end' | 'retrieval' | 'stream_chunk' | 'error' | 'info' | 'emotion_update' | 'graph_started' | 'graph_completed' | 'llm_started' | 'llm_completed';
  label: string;
  message: string;
  payload?: any;
}

export interface HITLRequest {
  interrupt_id: string;
  tool: string;
  prompt: string;
  data: any;
}

export type ModelTier = 'GPT-5.4-mini';
export type ReasoningEffort = 'Low' | 'Medium' | 'High';

export interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
}
