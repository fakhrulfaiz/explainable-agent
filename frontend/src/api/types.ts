// API Response Types
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  timestamp: string;
}

export interface ApiError {
  error: string;
  detail?: string;
  timestamp: string;
}

// Chat API Types
export interface ChatRequest {
  message: string;
  history?: ChatMessage[];
}

export interface ChatResponse {
  response: string;
  explanation?: string;
  reasoning_steps?: string[];
  confidence?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  explanation?: string;
}

// Agent API Types
export interface AgentConfig {
  model: string;
  temperature: number;
  max_tokens: number;
}

export interface AgentStatus {
  status: 'online' | 'offline' | 'processing';
  version: string;
  uptime: number;
}

// Approval API Types
export interface ApprovalRequest {
  message_id: string;
  content: string;
  approved: boolean;
  feedback?: string;
}

export interface ApprovalResponse {
  success: boolean;
  message: string;
}

// Query API Types (matching your backend schemas)
export interface QueryRequest {
  query: string;
}

export interface QueryResponse {
  success: boolean;
  data?: any;
  message?: string;
  timestamp: string;
}

export interface EnhancedQueryResponse {
  success: boolean;
  query: string;
  result: {
    Summary: string;
    details: string;
    source: string;
    inference: string;
    extra_explanation: string;
  };
  explanation_steps: Array<{
    step_number: number;
    output: string;
    confidence: number;
    why_chosen: string;
    timestamp: string;
  }>;
  timestamp: string;
}

// Health Check Types
export interface HealthResponse {
  status: string;
  timestamp: string;
  version: string;
}
