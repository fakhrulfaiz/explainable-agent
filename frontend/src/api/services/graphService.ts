import { apiClient } from '../client';
import { API_ENDPOINTS } from '../endpoints';
import { StartRequest, ResumeRequest, GraphResponse, GraphStatus } from '../../types/chat';

// Get the base URL from the environment
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Extend the Window interface to include our custom property
declare global {
  interface Window {
    _hasReceivedStatusEvent?: { [url: string]: boolean };
  }
}

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

  static async startStreamingGraph(request: StartRequest): Promise<GraphResponse> {
    try {
      const response = await apiClient.post<GraphResponse>(
        API_ENDPOINTS.STREAMING_GRAPH_START,
        request
      );
      return response;
    } catch (error) {
      console.error('Failed to start streaming graph:', error);
      throw error;
    }
  }

  static async resumeStreamingGraph(request: ResumeRequest): Promise<GraphResponse> {
    try {
      const response = await apiClient.post<GraphResponse>(
        API_ENDPOINTS.STREAMING_GRAPH_RESUME,
        request
      );
      return response;
    } catch (error) {
      console.error('Failed to resume streaming graph:', error);
      throw error;
    }
  }


  static streamResponse(thread_id: string, onMessageCallback: (data: any) => void, onErrorCallback: (error: Error) => void, onCompleteCallback: () => void) {
    // Create a new EventSource connection to the streaming endpoint
    const eventSource = new EventSource(`${BASE_URL}${API_ENDPOINTS.STREAMING_GRAPH_STREAM(thread_id)}`);
    
    // Handle token events (content streaming)
    eventSource.addEventListener('token', (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageCallback({ content: data.content, node: data.node, type: data.type });
      } catch (error) {
        console.error("Error parsing token event:", error, "Raw data:", event.data);
        onErrorCallback(error as Error);
      }
    });
    
    // Handle status events (user_feedback, finished)
    eventSource.addEventListener('status', (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageCallback({ status: data.status });
        
        // Mark that we've received a status event for this connection
        // This helps us distinguish between normal completion and errors
        if (!window._hasReceivedStatusEvent) {
          window._hasReceivedStatusEvent = {};
        }
        window._hasReceivedStatusEvent[eventSource.url] = true;
        console.log("Received status event, marking connection for normal closure");
      } catch (error) {
        console.error("Error parsing status event:", error, "Raw data:", event.data);
        onErrorCallback(error as Error);
      }
    });
    
    // Handle start/resume events
    eventSource.addEventListener('start', (event) => {
      console.log("Stream started:", event.data);
    });
    
    eventSource.addEventListener('resume', (event) => {
      console.log("Stream resumed:", event.data);
    });
    
    // Handle message events (complete messages) - normalize shape to match 'token'
    eventSource.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageCallback({ content: data.content, node: data.node, type: data.type || 'message' });
      } catch (error) {
        console.error("Error parsing message event:", error, "Raw data:", event.data);
        onErrorCallback(error as Error);
      }
    });
    
    // Handle errors
    eventSource.onerror = (error) => {
      console.log("SSE connection state change - readyState:", eventSource.readyState);
      
      // Check if we've received a status event indicating completion
      const hasReceivedStatusEvent = window._hasReceivedStatusEvent && window._hasReceivedStatusEvent[eventSource.url];
      
      if (hasReceivedStatusEvent) {
        console.log("Stream completed normally after receiving status event");
        eventSource.close();
        onCompleteCallback();
        return;
      }
      
      // Only call the error callback if it's a real error, not a normal close
      if (eventSource.readyState !== EventSource.CLOSED && eventSource.readyState !== EventSource.CONNECTING) {
        console.error("SSE connection error:", error);
        eventSource.close();
        // Pass a proper error object with a message to avoid 'undefined' errors
        onErrorCallback(new Error("Connection error or server disconnected"));
      } else {
        // If it's a normal close or reconnecting, call the complete callback
        console.log("Stream completed normally");
        onCompleteCallback();
      }
    };
    
    // Return the eventSource so it can be closed externally if needed
    return eventSource;
  }
     
}

export default GraphService;
