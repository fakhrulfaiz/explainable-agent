import { apiClient } from '../client';
import { API_ENDPOINTS } from '../endpoints';
import { 
  ChatRequest, 
  ChatResponse, 
  ChatMessage, 
  ApiResponse 
} from '../types';

export class ChatService {
  /**
   * Send a message to the chat API
   */
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    return apiClient.post<ChatResponse>(API_ENDPOINTS.CHAT, request);
  }

  /**
   * Get chat history
   */
  async getChatHistory(): Promise<ChatMessage[]> {
    return apiClient.get<ChatMessage[]>(API_ENDPOINTS.CHAT_HISTORY);
  }

  /**
   * Clear chat history
   */
  async clearChatHistory(): Promise<ApiResponse> {
    return apiClient.delete<ApiResponse>(API_ENDPOINTS.CHAT_HISTORY);
  }

  /**
   * Stream chat response (for real-time responses)
   */
  async streamMessage(
    request: ChatRequest,
    onChunk: (chunk: string) => void,
    onComplete: (response: ChatResponse) => void,
    onError: (error: Error) => void
  ): Promise<void> {
    try {
      // This would be implemented for streaming responses
      // For now, falling back to regular message
      const response = await this.sendMessage(request);
      onComplete(response);
    } catch (error) {
      onError(error as Error);
    }
  }
}

export const chatService = new ChatService();
export default chatService;
