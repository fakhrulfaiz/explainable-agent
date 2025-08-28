import { apiClient } from '../client';
import { API_ENDPOINTS } from '../endpoints';
import { 
  ApprovalRequest, 
  ApprovalResponse 
} from '../types';

export class ApprovalService {
  
  async approveMessage(messageId: string, content: string, feedback?: string): Promise<ApprovalResponse> {
    const request: ApprovalRequest = {
      message_id: messageId,
      content,
      approved: true,
      feedback
    };
    
    return apiClient.post<ApprovalResponse>(API_ENDPOINTS.APPROVE_MESSAGE, request);
  }

  async disapproveMessage(messageId: string, content: string, feedback?: string): Promise<ApprovalResponse> {
    const request: ApprovalRequest = {
      message_id: messageId,
      content,
      approved: false,
      feedback
    };
    
    return apiClient.post<ApprovalResponse>(API_ENDPOINTS.DISAPPROVE_MESSAGE, request);
  }

  /**
   * Submit feedback for a message
   */
  async submitFeedback(messageId: string, content: string, feedback: string): Promise<ApprovalResponse> {
    const request: ApprovalRequest = {
      message_id: messageId,
      content,
      approved: false, // Feedback implies need for improvement
      feedback
    };
    
    return apiClient.post<ApprovalResponse>(API_ENDPOINTS.DISAPPROVE_MESSAGE, request);
  }
}

export const approvalService = new ApprovalService();
export default approvalService;
