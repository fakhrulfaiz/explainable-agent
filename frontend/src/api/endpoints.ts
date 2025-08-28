// API endpoint constants
export const API_ENDPOINTS = {
  // Chat endpoints
  CHAT: '/chat',
  CHAT_HISTORY: '/chat/history',
  
  // Query endpoints (matching your backend)
  QUERY: '/query',
  ENHANCED_QUERY: '/enhanced-query',
  
  // Agent endpoints
  AGENT_CONFIG: '/agent/config',
  AGENT_STATUS: '/agent/status',
  
  // Approval endpoints
  APPROVE_MESSAGE: '/approval/approve',
  DISAPPROVE_MESSAGE: '/approval/disapprove',
  
  // Health endpoints
  HEALTH: '/health',
  
  // Log endpoints
  LOGS: '/logs',
  LOG_DETAIL: (logId: string) => `/logs/${logId}`,
  
  // Graph endpoints
  GRAPH_START: '/graph/start',
  GRAPH_RESUME: '/graph/resume',
  GRAPH_STATUS: (threadId: string) => `/graph/status/${threadId}`,
} as const;

// Helper function to build URLs
export const buildUrl = (endpoint: string, params?: Record<string, string | number>) => {
  if (!params) return endpoint;
  
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    searchParams.append(key, value.toString());
  });
  
  return `${endpoint}?${searchParams.toString()}`;
};

export default API_ENDPOINTS;
