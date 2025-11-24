import { apiClient } from '../client';

export interface CheckpointSummary {
  checkpoint_id: string;
  thread_id: string;
  timestamp: string;
  message_type?: 'message' | 'explorer' | 'visualization' | 'structured';
  message_id: number;
  query?: string;
}

export interface CheckpointListResponse {
  success: boolean;
  data: CheckpointSummary[];
  message: string;
  total: number;
}

export class ExecutionHistoryService {
  private static client = apiClient;

  /**
   * Get all checkpoints for the current user across all threads
   */
  static async getAllCheckpoints(limit = 50, skip = 0): Promise<{ checkpoints: CheckpointSummary[]; total: number }> {
    const response = await this.client.get<CheckpointListResponse>(
      `/chat-history/checkpoints?limit=${limit}&skip=${skip}`
    );
    if (!response.success) {
      throw new Error(response.message || 'Failed to get checkpoints');
    }
    return { checkpoints: response.data, total: response.total };
  }
}

