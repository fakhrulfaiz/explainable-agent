import { apiClient } from '../client';
import { API_ENDPOINTS } from '../endpoints';
import { StartRequest, ResumeRequest, GraphResponse, GraphStatus } from '../../types/chat';

/**
 * Service for graph-based API interactions
 */
export class GraphService {
  
 
  static async startGraph(request: StartRequest): Promise<GraphResponse> {
    try {
      const response = await apiClient.post<GraphResponse>(
        API_ENDPOINTS.GRAPH_START,
        request
      );
      return response;
    } catch (error) {
      console.error('Failed to start graph:', error);
      throw error;
    }
  }

  static async resumeGraph(request: ResumeRequest): Promise<GraphResponse> {
    try {
      const response = await apiClient.post<GraphResponse>(
        API_ENDPOINTS.GRAPH_RESUME,
        request
      );
      return response;
    } catch (error) {
      console.error('Failed to resume graph:', error);
      throw error;
    }
  }

  /**
   * Get the status of a graph execution
   */
  static async getGraphStatus(threadId: string): Promise<GraphStatus> {
    try {
      const response = await apiClient.get<GraphStatus>(
        API_ENDPOINTS.GRAPH_STATUS(threadId)
      );
      return response;
    } catch (error) {
      console.error('Failed to get graph status:', error);
      throw error;
    }
  }

  /**
   * Check if a thread has an active graph execution
   */
  static async hasActiveGraph(threadId: string): Promise<boolean> {
    try {
      const response = await this.getGraphStatus(threadId);
      return response.execution_status === 'running' || response.execution_status === 'user_feedback';
    } catch (error) {
      // If we can't get the status, assume no active graph
      return false;
    }
  }


  static async approveAndContinue(threadId: string): Promise<GraphResponse> {
    return this.resumeGraph({
      thread_id: threadId,
      review_action: 'approved'
    });
  }

  static async provideFeedbackAndContinue(
    threadId: string, 
    feedback: string
  ): Promise<GraphResponse> {
    return this.resumeGraph({
      thread_id: threadId,
      review_action: 'feedback',
      human_comment: feedback
    });
  }

  static async cancelExecution(threadId: string): Promise<GraphResponse> {
    return this.resumeGraph({
      thread_id: threadId,
      review_action: 'cancelled'
    });
  }
}

export default GraphService;
