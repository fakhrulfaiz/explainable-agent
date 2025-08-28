import { apiClient } from '../client';
import { API_ENDPOINTS } from '../endpoints';
import { 
  QueryRequest, 
  QueryResponse, 
  EnhancedQueryResponse,
  AgentConfig, 
  AgentStatus,
  ApiResponse 
} from '../types';

export class AgentService {
  /**
   * Send a query to the explainable agent
   */
  async sendQuery(request: QueryRequest): Promise<QueryResponse> {
    return apiClient.post<QueryResponse>(API_ENDPOINTS.QUERY, request);
  }

  /**
   * Send an enhanced query to get detailed explanations
   */
  async sendEnhancedQuery(request: QueryRequest): Promise<EnhancedQueryResponse> {
    return apiClient.post<EnhancedQueryResponse>(API_ENDPOINTS.ENHANCED_QUERY, request);
  }

  /**
   * Get agent configuration
   */
  async getConfig(): Promise<AgentConfig> {
    return apiClient.get<AgentConfig>(API_ENDPOINTS.AGENT_CONFIG);
  }

  /**
   * Update agent configuration
   */
  async updateConfig(config: Partial<AgentConfig>): Promise<ApiResponse> {
    return apiClient.put<ApiResponse>(API_ENDPOINTS.AGENT_CONFIG, config);
  }

  /**
   * Get agent status
   */
  async getStatus(): Promise<AgentStatus> {
    return apiClient.get<AgentStatus>(API_ENDPOINTS.AGENT_STATUS);
  }

  /**
   * Health check
   */
  async healthCheck(): Promise<ApiResponse> {
    return apiClient.get<ApiResponse>(API_ENDPOINTS.HEALTH);
  }
}

export const agentService = new AgentService();
export default agentService;
