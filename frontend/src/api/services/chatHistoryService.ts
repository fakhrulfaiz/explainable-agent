import { apiClient } from '../client';
import { ChatMessage } from '../types';

export interface ChatThread {
  thread_id: string;
  title?: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

export interface ChatThreadSummary {
  thread_id: string;
  title?: string;
  last_message?: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateChatRequest {
  title?: string;
  initial_message?: string;
}

export interface AddMessageRequest {
  thread_id: string;
  sender: 'user' | 'assistant';
  content: string;
  message_type?: 'message' | 'explorer';
  checkpoint_id?: string;
  
  // Additional fields from frontend Message interface
  message_id?: number;
  needs_approval?: boolean;
  approved?: boolean;
  disapproved?: boolean;
  is_error?: boolean;
  is_feedback?: boolean;
  has_timed_out?: boolean;
  can_retry?: boolean;
  retry_action?: 'approve' | 'feedback' | 'cancel';
  thread_id_ref?: string;
  metadata?: { [key: string]: any };
}

export interface ChatHistoryResponse {
  success: boolean;
  data?: ChatThread;
  message: string;
}

export interface ChatListResponse {
  success: boolean;
  data: ChatThreadSummary[];
  message: string;
  total: number;
}

export class ChatHistoryService {
  private static client = apiClient;

  /**
   * Create a new chat thread
   */
  static async createThread(request: CreateChatRequest): Promise<ChatThread> {
    const response = await this.client.post<ChatHistoryResponse>('/chat-history/create', request);
    if (!response.success || !response.data) {
      throw new Error(response.message || 'Failed to create chat thread');
    }
    return response.data;
  }

  /**
   * Get all chat threads
   */
  static async getAllThreads(limit = 50, skip = 0): Promise<{ threads: ChatThreadSummary[], total: number }> {
    const response = await this.client.get<ChatListResponse>(`/chat-history/threads?limit=${limit}&skip=${skip}`);
    if (!response.success) {
      throw new Error(response.message || 'Failed to get chat threads');
    }
    return { threads: response.data, total: response.total };
  }

  /**
   * Get a specific chat thread with full history
   */
  static async getThread(threadId: string): Promise<ChatThread> {
    const response = await this.client.get<ChatHistoryResponse>(`/chat-history/thread/${threadId}`);
    if (!response.success || !response.data) {
      throw new Error(response.message || 'Failed to get chat thread');
    }
    return response.data;
  }

  /**
   * Add a message to an existing thread
   */
  static async addMessage(request: AddMessageRequest): Promise<void> {
    const response = await this.client.post<{ success: boolean; message: string }>('/chat-history/add-message', request);
    if (!response.success) {
      throw new Error(response.message || 'Failed to add message');
    }
  }

  /**
   * Restore a chat thread for continuing conversation
   */
  static async restoreThread(threadId: string): Promise<ChatThread> {
    const response = await this.client.post<ChatHistoryResponse>(`/chat-history/thread/${threadId}/restore`, {});
    if (!response.success || !response.data) {
      throw new Error(response.message || 'Failed to restore chat thread');
    }
    return response.data;
  }

  /**
   * Update thread title
   */
  static async updateThreadTitle(threadId: string, title: string): Promise<void> {
    const response = await this.client.put<{ success: boolean; message: string }>(`/chat-history/thread/${threadId}/title?title=${encodeURIComponent(title)}`, {});
    if (!response.success) {
      throw new Error(response.message || 'Failed to update thread title');
    }
  }

  /**
   * Delete a chat thread
   */
  static async deleteThread(threadId: string): Promise<void> {
    const response = await this.client.delete<{ success: boolean; message: string }>(`/chat-history/thread/${threadId}`);
    if (!response.success) {
      throw new Error(response.message || 'Failed to delete chat thread');
    }
  }
}
