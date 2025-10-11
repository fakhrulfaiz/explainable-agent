import { apiClient } from '../client';

export interface VisualizationDataRequest {
  thread_id: string;
  checkpoint_id: string;
}

export interface VisualizationDataResponse {
  success: boolean;
  data?: any; // Visualization data format
  message: string;
}

export class VisualizationService {
  private static client = apiClient;

  /**
   * Fetch visualization data from a specific checkpoint
   */
  static async getVisualizationData(threadId: string, checkpointId: string): Promise<any> {
    const response = await this.client.get<VisualizationDataResponse>(
      `/graph/visualization/data?thread_id=${threadId}&checkpoint_id=${checkpointId}`
    );
    if (!response.success || !response.data) {
      throw new Error(response.message || 'Failed to fetch visualization data');
    }
    return response.data;
  }

  /**
   * Get visualization data from graph result
   */
  static async getVisualizationDataFromResult(threadId: string): Promise<any> {
    const response = await this.client.get<VisualizationDataResponse>(
      `/graph/stream/result/${threadId}`
    );
    if (!response.success || !response.data) {
      throw new Error(response.message || 'Failed to fetch visualization data from result');
    }
    return response.data;
  }
}

export const visualizationService = new VisualizationService();
