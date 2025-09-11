import { apiClient } from '../client';

export interface ExplorerDataRequest {
  thread_id: string;
  checkpoint_id: string;
}

export interface ExplorerDataResponse {
  success: boolean;
  data?: any; // ExplorerResult format
  message: string;
}

export class ExplorerService {
  private static client = apiClient;

  /**
   * Fetch explorer data from a specific checkpoint
   */
  static async getExplorerData(threadId: string, checkpointId: string): Promise<any> {
    const response = await this.client.get<ExplorerDataResponse>(
      `/explorer/data?thread_id=${threadId}&checkpoint_id=${checkpointId}`
    );
    if (!response.success || !response.data) {
      throw new Error(response.message || 'Failed to fetch explorer data');
    }
    return response.data;
  }
}

export const explorerService = new ExplorerService();
