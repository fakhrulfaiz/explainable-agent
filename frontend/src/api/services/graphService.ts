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
    
    // Enhanced error handling and recovery
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 3;
    let lastHeartbeat = Date.now();
    const heartbeatTimeout = 30000; // 30 seconds
    
    // Heartbeat monitoring
    const heartbeatInterval = setInterval(() => {
      if (Date.now() - lastHeartbeat > heartbeatTimeout) {
        console.warn('⚠️ Stream heartbeat timeout, connection may be stale');
        clearInterval(heartbeatInterval);
        eventSource.close();
        onErrorCallback(new Error('Stream connection timeout'));
      }
    }, 5000);
    
    // Handle token events (content streaming)
    eventSource.addEventListener('token', (event) => {
      try {
        lastHeartbeat = Date.now(); // Update heartbeat
        const data = JSON.parse(event.data);
        onMessageCallback({ content: data.content, node: data.node, type: data.type });
      } catch (error) {
        console.error("❌ Error parsing token event:", error, "Raw data:", event.data);
        onErrorCallback(error as Error);
      }
    });
    
    // Handle status events (user_feedback, finished)
    eventSource.addEventListener('status', (event) => {
      try {
        lastHeartbeat = Date.now(); // Update heartbeat
        const data = JSON.parse(event.data);
        // Pass through response_type if it exists in the status event
        onMessageCallback({ 
          status: data.status, 
          response_type: data.response_type  // Include response_type from backend
        });
        
        // Mark that we've received a status event for this connection
        // This helps us distinguish between normal completion and errors
        if (!window._hasReceivedStatusEvent) {
          window._hasReceivedStatusEvent = {};
        }
        window._hasReceivedStatusEvent[eventSource.url] = true;
        console.log("✅ Received status event, marking connection for normal closure");
      } catch (error) {
        console.error("❌ Error parsing status event:", error, "Raw data:", event.data);
        onErrorCallback(error as Error);
      }
    });

    // Handle completed events with final payload wrapper
    eventSource.addEventListener('completed', (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data);
        const inner = payload && payload.data ? payload.data : payload;
   
        onMessageCallback({ status: 'completed_payload', graph: inner });
        // Mark normal closure
        if (!window._hasReceivedStatusEvent) {
          window._hasReceivedStatusEvent = {};
        }
        window._hasReceivedStatusEvent[eventSource.url] = true;
      } catch (error) {
        console.error('Error parsing completed event:', error, 'Raw data:', (event as MessageEvent).data);
        onErrorCallback(error as Error);
      }
    });

    // Handle visualizations_ready events
    eventSource.addEventListener('visualizations_ready', (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data);
        const inner = payload && payload.data ? payload.data : payload;
        onMessageCallback({ 
          status: 'visualizations_ready', 
          visualizations: inner?.visualizations || [],
          thread_id: inner?.thread_id,
          checkpoint_id: inner?.checkpoint_id,
          types: inner?.types
        });
      } catch (error) {
        console.error('Error parsing visualizations_ready event:', error, 'Raw data:', (event as MessageEvent).data);
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
    
    // Handle tool call events
    eventSource.addEventListener('tool_call', (event) => {
      try {
        lastHeartbeat = Date.now();
        onMessageCallback({ 
          status: 'tool_call', 
          eventData: event.data
        });
      } catch (error) {
        console.error("Error parsing tool_call event:", error, "Raw data:", event.data);
        onErrorCallback(error as Error);
      }
    });
    
    // Handle tool result events
    eventSource.addEventListener('tool_result', (event) => {
      try {
        lastHeartbeat = Date.now();
        console.log("✅ FRONTEND: Received tool_result event:", event.data);
        const data = JSON.parse(event.data);
        console.log("✅ FRONTEND: Parsed tool_result data:", data);
        // Pass through as status event so it reaches onStatus callback
        onMessageCallback({ 
          status: 'tool_result', 
          eventData: event.data  // Pass the raw JSON string so ChatComponent can parse it
        });
      } catch (error) {
        console.error("Error parsing tool_result event:", error, "Raw data:", event.data);
        onErrorCallback(error as Error);
      }
    });
    
    // Handle errors with enhanced recovery
    eventSource.onerror = (error) => {
      console.log("🔄 SSE connection state change - readyState:", eventSource.readyState);
      clearInterval(heartbeatInterval); // Clear heartbeat monitoring
      
      // Check if we've received a status event indicating completion
      const hasReceivedStatusEvent = window._hasReceivedStatusEvent && window._hasReceivedStatusEvent[eventSource.url];
      
      if (hasReceivedStatusEvent) {
        console.log("✅ Stream completed normally after receiving status event");
        eventSource.close();
        onCompleteCallback();
        return;
      }
      
      // Handle reconnection attempts for transient errors
      if (eventSource.readyState === EventSource.CONNECTING && reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        console.log(`🔄 Reconnection attempt ${reconnectAttempts}/${maxReconnectAttempts}`);
        
        // Wait before next attempt with exponential backoff
        setTimeout(() => {
          if (eventSource.readyState === EventSource.CLOSED) {
            console.log('🔄 Attempting to recover stream connection...');
            // Note: EventSource handles reconnection automatically, 
            // but we can implement custom recovery logic here if needed
          }
        }, Math.pow(2, reconnectAttempts) * 1000);
        return;
      }
      
      // Only call the error callback if it's a real error, not a normal close
      if (eventSource.readyState !== EventSource.CLOSED && eventSource.readyState !== EventSource.CONNECTING) {
        console.error("❌ SSE connection error:", error);
        eventSource.close();
        
        // Enhanced error messaging
        const errorMessage = reconnectAttempts >= maxReconnectAttempts 
          ? `Connection failed after ${maxReconnectAttempts} retry attempts`
          : "Connection error or server disconnected";
        
        onErrorCallback(new Error(errorMessage));
      } else {
        // If it's a normal close or reconnecting, call the complete callback
        console.log("✅ Stream completed normally");
        onCompleteCallback();
      }
    };
    
    // Enhanced cleanup function
    const cleanup = () => {
      clearInterval(heartbeatInterval);
      if (eventSource.readyState !== EventSource.CLOSED) {
        eventSource.close();
      }
    };
    
    // Return just the eventSource for backward compatibility
    return eventSource;
  }

  /**
   * Recover messages from backend when streaming fails
   * This helps ensure message consistency between frontend and backend
   */
  // static async recoverMessages(threadId: string): Promise<any[]> {
  //   try {
  //     console.log('🔄 Attempting to recover messages from backend...');
      
  //     // Import ChatHistoryService dynamically to avoid circular dependencies
  //     const { ChatHistoryService } = await import('./chatHistoryService');
  //     const messagesStatus = await ChatHistoryService.getMessagesStatus(threadId);
      
  //     console.log(`✅ Recovered ${messagesStatus.message_count} messages from backend`);
  //     return messagesStatus.messages;
  //   } catch (error) {
  //     console.error('❌ Failed to recover messages from backend:', error);
  //     throw error;
  //   }
  // }

  // /**
  //  * Sync message status with backend
  //  * This ensures frontend state matches backend state
  //  */
  // static async syncMessageStatus(threadId: string, messageId: number, status: any): Promise<void> {
  //   try {
  //     const { ChatHistoryService } = await import('./chatHistoryService');
  //     await ChatHistoryService.updateMessageFlags(threadId, {
  //       message_id: messageId,
  //       ...status
  //     });
  //     console.log(`✅ Synced message ${messageId} status with backend`);
  //   } catch (error) {
  //     console.error(`❌ Failed to sync message ${messageId} status:`, error);
  //     throw error;
  //   }
  // }
     
}

export default GraphService;
