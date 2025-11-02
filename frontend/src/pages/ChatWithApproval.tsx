import React, { useState } from 'react';
import { ChatComponent, ExplorerPanel, VisualizationPanel } from '../components';
// import ChatThreadSelector from '../components/ChatThreadSelector'; // Commented for future use
import { EnhancedSidebar2 } from '../components';
import { Message, HandlerResponse } from '../types/chat';
import { GraphService } from '../api/services/graphService';
import { ChatHistoryService } from '../api/services/chatHistoryService';
import { ExplorerService } from '../api/services/explorerService';
import { VisualizationService } from '../api/services/visualizationService';
import { useUIState } from '../contexts/UIStateContext';

const ChatWithApproval: React.FC = () => {
  // Use the UI state context
  const { state, setExecutionStatus, setThreadId, setLoading } = useUIState();
  // Streaming preference from UI state (replaces separate StreamingContext)
  const useStreaming = state.useStreaming;
  React.useEffect(() => {
    // Observe context value updates
  }, [useStreaming]);
  
 // Local state for UI-specific concerns
  const [chatKey, setChatKey] = useState<number>(0); // For resetting chat
  const [selectedChatThreadId, setSelectedChatThreadId] = useState<string | null>(null);
  const [explorerOpen, setExplorerOpen] = useState<boolean>(false);
  const [explorerData, setExplorerData] = useState<any | null>(null);
  const [loadingThread, setLoadingThread] = useState<boolean>(false);
  // Visualization panel state
  const [visualizationOpen, setVisualizationOpen] = useState<boolean>(false);
  const [visualizationCharts, setVisualizationCharts] = useState<any[] | null>(null);
  const [restoredMessages, setRestoredMessages] = useState<Message[]>([]);
  const [sidebarExpanded, setSidebarExpanded] = useState<boolean>(true); // Track sidebar expansion for margin
  const [currentThreadTitle, setCurrentThreadTitle] = useState<string>(''); // Thread title state

  // Streaming connection reference
  const eventSourceRef = React.useRef<EventSource | null>(null);
  
  // Thread ID reference to handle race conditions
  const currentThreadIdRef = React.useRef<string | null>(null);

  const convertChatHistoryToMessages = (chatMessages: any[]): Message[] => {
    return chatMessages.map((msg, index) => {
      const approved: boolean = !!msg.approved;
      const disapproved: boolean = !!msg.disapproved;
      const needsApprovalFlag: boolean = !!msg.needs_approval;
      const needsApprovalComputed = needsApprovalFlag && !approved && !disapproved;

      return {
        id: (typeof msg.message_id === 'number' ? msg.message_id : (Date.now() + index)),
        role: (msg.sender === 'assistant' ? 'assistant' : 'user'),
        content: String(msg.content ?? ''),
        timestamp: new Date(msg.timestamp),
        needsApproval: needsApprovalComputed,
        approved,
        disapproved,
        isError: !!msg.is_error,
        isFeedback: !!msg.is_feedback,
        hasTimedOut: !!msg.has_timed_out,
        canRetry: !!msg.can_retry,
        retryAction: msg.retry_action || undefined,
        threadId: msg.thread_id || selectedChatThreadId || undefined,
        messageType: (msg.message_type as any) || 'message',
        checkpointId: msg.checkpoint_id
      } as Message;
    });
  };


  const restoreDataIfNeeded = async (messages: Message[], threadId: string) => {
    const explorerMessages = messages.filter(msg => 
      msg.messageType === 'explorer' && 
      msg.checkpointId && 
      msg.role === 'assistant'
    );

    const visualizationMessages = messages.filter(msg => 
      msg.messageType === 'visualization' && 
      msg.role === 'assistant'
    );

    if (explorerMessages.length > 0 || visualizationMessages.length > 0) {
      try {
        const explorerDataMap = new Map();
        const visualizationDataMap = new Map();
        
        // Restore explorer data
        for (const explorerMessage of explorerMessages) {
          try {
            const explorerData = await ExplorerService.getExplorerData(
              threadId,
              explorerMessage.checkpointId!
            );
            
            if (explorerData) {
              explorerDataMap.set(explorerMessage.id, explorerData);
            }
          } catch (error) {
            console.error('Failed to restore explorer data for checkpoint:', explorerMessage.checkpointId, error);
          }
        }
        
        for (const visualizationMessage of visualizationMessages) {
          try {
            const visualizationData = await VisualizationService.getVisualizationData(
              threadId,
              visualizationMessage.checkpointId || ''
            );
            if (visualizationData) {
              visualizationDataMap.set(visualizationMessage.id, visualizationData.visualizations);
            }
          } catch (error) {
            console.error('Failed to restore visualization data for checkpoint:', visualizationMessage.checkpointId, error);
          }
        }
        
        // Update messages with both types of data
        const updatedMessages = messages.map(msg => {
          let updatedMsg = { ...msg };
          
          if (msg.messageType === 'explorer' && explorerDataMap.has(msg.id)) {
            const explorerData = explorerDataMap.get(msg.id);
            updatedMsg = {
              ...updatedMsg,
              metadata: { 
                ...updatedMsg.metadata,
                explorerData 
              }
            };
          }
          
          if (msg.messageType === 'visualization' && visualizationDataMap.has(msg.id)) {
            const visualizations = visualizationDataMap.get(msg.id);
            updatedMsg = {
              ...updatedMsg,
              metadata: { 
                ...updatedMsg.metadata,
                visualizations: visualizations
              }
            };
          }
          
          return updatedMsg;
        });
        
        setRestoredMessages(updatedMessages);

        // If any restored message needs approval, set execution status to user_feedback
        if (updatedMessages.some(m => m.needsApproval)) {
          setExecutionStatus('user_feedback');
        }
        
        // Set the latest explorer data
        const lastExplorerMessage = explorerMessages[explorerMessages.length - 1];
        if (lastExplorerMessage) {
          const lastUpdatedMessage = updatedMessages.find(msg => msg.id === lastExplorerMessage.id);
          if (lastUpdatedMessage?.metadata?.explorerData) {
            setExplorerData(lastUpdatedMessage.metadata.explorerData);
          }
        }
        
        // Set the latest visualization data
        const lastVisualizationMessage = visualizationMessages[visualizationMessages.length - 1];
        if (lastVisualizationMessage) {
          const lastUpdatedMessage = updatedMessages.find(msg => msg.id === lastVisualizationMessage.id);
          if (lastUpdatedMessage?.metadata?.visualizations) {
            setVisualizationCharts(lastUpdatedMessage.metadata.visualizations);
          }
        }
        
      } catch (error) {
        console.error('Failed to restore data:', error);
      }
    } else {
      setRestoredMessages(messages);
      // If any restored message needs approval, set execution status to user_feedback
      if (messages.some(m => m.needsApproval)) {
        setExecutionStatus('user_feedback');
      }
    }
  };

  const handleOpenExplorer = (data: any) => {
    if (data) {
      // Ensure only one panel is open at a time
      setVisualizationOpen(false);
      setVisualizationCharts(null);
      setExplorerData(data);
      setExplorerOpen(true);
    }
  };

  const handleMessageCreated = async (_msg: Message) => {
    // All messages (user and assistant) are now saved by backend during graph execution
  };

  const handleMessageUpdated = async (msg: Message) => {
    // Handle persistent storage of message flag updates
    const threadId = currentThreadIdRef.current || state.currentThreadId || selectedChatThreadId || msg.threadId;
    if (!threadId) {
      console.error('No thread ID available for message update');
      return;
    }

    try {
      // Update message flags in the database
      await ChatHistoryService.updateMessageFlags(threadId, {
        message_id: msg.id,
        needs_approval: msg.needsApproval,
        approved: msg.approved,
        disapproved: msg.disapproved,
        is_error: msg.isError,
        is_feedback: msg.isFeedback,
        has_timed_out: msg.hasTimedOut,
        can_retry: msg.canRetry,
        retry_action: msg.retryAction
      });
      
    } catch (error) {
      console.error('Failed to update message flags in database:', error);
   
    }
  };

  React.useEffect(() => {
    (window as any).openExplorer = handleOpenExplorer;
    (window as any).openVisualization = (charts: any[]) => {
      if (charts && charts.length > 0) {
        setExplorerOpen(false);
        setExplorerData(null);
        setVisualizationCharts(charts);
        setVisualizationOpen(true);
      }
    };
    return () => {
      delete (window as any).openExplorer;
      delete (window as any).openVisualization;
    };
  }, []);

  // Cleanup EventSource on unmount
  React.useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const createNewChatThread = async (initialMessage?: string): Promise<string> => {
    try {
      const thread = await ChatHistoryService.createThread({
        title: initialMessage || 'New Chat',
        initial_message: initialMessage
      });
      return thread.thread_id;
    } catch (error) {
      console.error('Error creating chat thread:', error);
      throw error;
    }
  };
 
  // Note: Message storage is now handled automatically by ChatComponent via onMessageCreated
  // This storeMessage function is kept only for user messages in specific flows

  // Enhanced streaming message handler
  const startStreamingForMessage = async (
    messageContent: string, 
    streamingMessageId: number,
    chatThreadId: string,
    updateMessageCallback: (id: number, content: string) => void,
    onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error' | 'tool_call' | 'tool_result' | 'completed_payload' | 'visualizations_ready', eventData?: string, responseType?: 'answer' | 'replan' | 'cancel') => void,
    usePlanning: boolean = true,
    useExplainer: boolean = true
  ): Promise<void> => {
    try {
      const startResponse = await GraphService.startStreamingGraph({
        human_request: messageContent,
        thread_id: chatThreadId,
        use_planning: usePlanning,
        use_explainer: useExplainer
      });

      setThreadId(startResponse.thread_id);
      eventSourceRef.current = GraphService.streamResponse(
        startResponse.thread_id,
        (data) => {
          if (data.content) {
            updateMessageCallback(streamingMessageId, data.content);
          } else if (data.status) {
            if (data.status === 'completed_payload') {
              // Handle explorer data from completed payload
              const graphData = data.graph;
              if (graphData && graphData.steps && graphData.steps.length > 0) {
                const explorerMessageId = Date.now() + Math.floor(Math.random() * 1000);
                const explorerMessage = {
                  id: explorerMessageId,
                  role: 'assistant',
                  content: 'Explorer data available',
                  timestamp: new Date(),
                  messageType: 'explorer',
                  checkpointId: graphData.checkpoint_id,
                  metadata: { explorerData: graphData },
                  threadId: chatThreadId
                };
                if (updateMessageCallback) {
                  updateMessageCallback(explorerMessageId, JSON.stringify(explorerMessage));
                }
              }
            } else if (data.status === 'visualizations_ready') {
              // Handle visualization data
              const visualizations = data.visualizations || [];
              if (visualizations.length > 0) {
                // Create a new message with its own ID for visualization data
                const vizMessageId = Date.now() + Math.floor(Math.random() * 1000) + 10000;
                const vizMessage = {
                  id: vizMessageId,
                  role: 'assistant',
                  content: 'Visualizations available',
                  timestamp: new Date(),
                  messageType: 'visualization',
                  checkpointId: data.checkpoint_id,
                  metadata: { visualizations: visualizations },
                  threadId: chatThreadId
                };

                if (updateMessageCallback) {
                  updateMessageCallback(vizMessageId, JSON.stringify(vizMessage));
                }
              }
              
            }
            else {
              setExecutionStatus(data.status);
            }
            
            if (onStatus) {
              onStatus(data.status, data.eventData, data.response_type);  // Pass eventData and response_type
            }
          }
        },
        (error) => {
          console.error('Streaming error:', error);
          setLoading(false);
          throw error;
        },
        () => {
          setLoading(false);
        }
      );

    } catch (error) {
      console.error('Failed to start streaming:', error);
      setLoading(false);
      throw error;
    }
  };

  const resumeStreamingForMessage = async (
    threadId: string,
    reviewAction: 'approved' | 'feedback' | 'cancelled',
    humanComment?: string,
    streamingMessageId?: number,
    updateMessageCallback?: (id: number, content: string) => void,
    onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error' | 'tool_call' | 'tool_result' | 'completed_payload' | 'visualizations_ready', eventData?: string, responseType?: 'answer' | 'replan' | 'cancel') => void
  ): Promise<void> => {
    try {
      await GraphService.resumeStreamingGraph({
        thread_id: threadId,
        review_action: reviewAction,
        human_comment: humanComment
      });


      eventSourceRef.current = GraphService.streamResponse(
        threadId,
        (data) => {
          if (data.content && streamingMessageId && updateMessageCallback) {
            updateMessageCallback(streamingMessageId, data.content);
          } else if (data.status) {
            if (data.status === 'completed_payload') {
              // Handle explorer data from completed payload
              const graphData = data.graph;
              if (graphData && graphData.steps && graphData.steps.length > 0) {
                // Create a new message with its own ID for explorer data
                const explorerMessageId = Date.now() + Math.floor(Math.random() * 1000);
                const explorerMessage = {
                  id: explorerMessageId,
                  role: 'assistant',
                  content: 'Explorer data available',
                  timestamp: new Date(),
                  messageType: 'explorer',
                  checkpointId: graphData.checkpoint_id,
                  metadata: { explorerData: graphData },
                  threadId: threadId
                };
                
                // Add the explorer message to the chat using updateMessageCallback with the new ID
                if (updateMessageCallback) {
                  updateMessageCallback(explorerMessageId, JSON.stringify(explorerMessage));
                }
                
                // Use the global window functions to open explorer
                if ((window as any).openExplorer) {
                  (window as any).openExplorer(graphData);
                }
              }
              // Don't append graph data to the streaming message content
              // The graph data is handled separately above for explorer messages
            } else if (data.status === 'visualizations_ready') {
              // Handle visualization data
              const visualizations = data.visualizations || [];
              if (visualizations.length > 0) {
                // Create a new message with its own ID for visualization data
                const vizMessageId = Date.now() + Math.floor(Math.random() * 1000) + 10000;
                const vizMessage = {
                  id: vizMessageId,
                  role: 'assistant',
                  content: 'Visualizations available',
                  timestamp: new Date(),
                  messageType: 'visualization',
                  checkpointId: data.checkpoint_id,
                  metadata: { visualizations: visualizations },
                  threadId: threadId
                };
                
                // Add the visualization message to the chat using updateMessageCallback with the new ID
                if (updateMessageCallback) {
                  updateMessageCallback(vizMessageId, JSON.stringify(vizMessage));
                }
                
                // Use the global window functions to open visualizations
                if ((window as any).openVisualization) {
                  (window as any).openVisualization(visualizations);
                }
              }
            }
            setExecutionStatus(data.status);
            if (onStatus) {
              onStatus(data.status, data.eventData, data.response_type);  // Pass response_type
            }
          }
        },
        (error) => {
          console.error('Resume streaming error:', error);
          setLoading(false);
          throw error;
        },
        () => {
          setLoading(false);
        }
      );

    } catch (error) {
      console.error('Failed to resume streaming:', error);
      setLoading(false);
      throw error;
    }
  };

  const handleSendMessage = async (message: string, _messageHistory: Message[], options?: { usePlanning?: boolean; useExplainer?: boolean; attachedFiles?: File[] }): Promise<HandlerResponse> => {
    // Close any open panels at start
    setExplorerData(null);
    setExplorerOpen(false);
    setVisualizationCharts(null);
    setVisualizationOpen(false);
    setLoading(true);
    setExecutionStatus('running');
    
    // Extract planning and explainer preferences from options (defaults to true)
    const usePlanning = options?.usePlanning ?? true;
    const useExplainer = options?.useExplainer ?? true;
    
    try {
      
      let chatThreadId = selectedChatThreadId;
      if (!chatThreadId) {
        chatThreadId = await createNewChatThread(message);
        // Immediately update the ref to avoid race conditions with message persistence
        currentThreadIdRef.current = chatThreadId;
        setSelectedChatThreadId(chatThreadId);
        setThreadId(chatThreadId);
      } else {
        currentThreadIdRef.current = chatThreadId;
      }
      
      if (!useStreaming) {
        // Original blocking API call
        const response = await GraphService.startGraph({
          human_request: message,
          thread_id: chatThreadId,
          use_planning: usePlanning,
          use_explainer: useExplainer
        });
        if (response.run_status === 'user_feedback') {
          setExecutionStatus('user_feedback');
          setLoading(false);
          
          const plan = response.plan || response.assistant_response || 'Plan generated - awaiting approval';
          const assistantResponse = `**Plan for your request:**\n\n${plan}\n\n**This plan requires your approval before execution.**`;

          return {
            message: assistantResponse,
            needsApproval: true,
            backendMessageId: response.assistant_message_id // Pass backend message ID
          };
        } else if (response.run_status === 'finished') {
          setExecutionStatus('finished');
          setLoading(false);
          
          const assistantResponse = response.assistant_response || 'Task completed successfully.'
          // Do not auto-open panels; allow clicking message card to open
          
          return {
            message: assistantResponse,
            needsApproval: false,
            checkpoint_id: response.checkpoint_id, // Add checkpoint ID for both explorer and visualization messages
            ...(response.steps && response.steps.length > 0 ? { explorerData: response } : {}),
            ...(response.visualizations && response.visualizations.length > 0 ? { visualizations: response.visualizations } : {})
          };
        } else if (response.run_status === 'error') {
          throw new Error(response.error || 'An error occurred while processing your request.');
        }

        const assistantResponse = response.assistant_response || 'Processing...';
        // Message will be stored automatically by ChatComponent via onMessageCreated
        return {
          message: assistantResponse,
          needsApproval: false
        };
      } else {
        // Streaming API call - return a promise that will be handled by the streaming logic
        return {
          message: '', // This will be filled by streaming
          needsApproval: false, // This will be determined by streaming status
          isStreaming: true,
          streamingHandler: async (
            streamingMessageId: number,
            updateMessageCallback: (id: number, content: string) => void,
            onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error' | 'tool_call' | 'tool_result' | 'completed_payload' | 'visualizations_ready', eventData?: string) => void
          ) => {
            await startStreamingForMessage(message, streamingMessageId, chatThreadId, updateMessageCallback, onStatus, usePlanning, useExplainer);
          }
        };
      }
    } catch (error) {
      console.error('Error in handleSendMessage:', error);
      setLoading(false);
      throw error;
    }
  };

  const handleApprove = async (_content: string, message: Message): Promise<HandlerResponse> => {
    const threadId = currentThreadIdRef.current || state.currentThreadId || selectedChatThreadId || message.threadId;
    
    if (!threadId) {
      throw new Error('No active thread to approve');
    }

    try {
      setLoading(true);
      setExecutionStatus('running');

      if (!useStreaming) {
        // Original blocking approach
        const response = await GraphService.approveAndContinue(threadId);

        if (response.run_status === 'finished') {
          const finalResponse = response.assistant_response || 'Task completed successfully.';
          
          let detailedResponse = finalResponse;
          if (response.steps && response.steps.length > 0) {
            detailedResponse += `\n\n**Execution Summary:**\n`;
            detailedResponse += `- Steps executed: ${response.steps.length}\n`;
            if (response.overall_confidence) {
              detailedResponse += `- Overall confidence: ${(response.overall_confidence * 100).toFixed(1)}%\n`;
            }
            if (response.total_time) {
              detailedResponse += `- Total time: ${response.total_time.toFixed(2)}s\n`;
            }
          }
          
          // Do not auto-open panels; allow clicking message card to open
          
          return {
            message: detailedResponse,
            needsApproval: false,
            checkpoint_id: response.checkpoint_id, // Add checkpoint ID for both explorer and visualization messages
            ...(response.steps && response.steps.length > 0 ? { explorerData: response } : {}),
            ...(response.visualizations && response.visualizations.length > 0 ? { visualizations: response.visualizations } : {})
          };
          
        } else if (response.run_status === 'error') {
          throw new Error(response.error || 'An error occurred during execution');
        } else {
          const assistantResponse = response.assistant_response || 'Execution in progress...';
          // Message will be stored automatically by ChatComponent via onMessageCreated
          return {
            message: assistantResponse,
            needsApproval: false
          };
        }
      } else {
        // Streaming approach
        return {
          message: '', // This will be filled by streaming
          needsApproval: false, // This will be determined by streaming status
          isStreaming: true,
          streamingHandler: async (
            streamingMessageId: number,
            updateMessageCallback: (id: number, content: string) => void,
            onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error' | 'tool_call' | 'tool_result' | 'completed_payload' | 'visualizations_ready', eventData?: string) => void
          ) => {
            await resumeStreamingForMessage(threadId, 'approved', undefined, streamingMessageId, updateMessageCallback, onStatus);
          }
        };
      }
      
    } catch (error) {
      console.error('Error approving plan:', error);
      setLoading(false);
      throw error;
    }
  };

  const handleFeedback = async (content: string, _message: Message): Promise<HandlerResponse> => {
    
    const threadId = currentThreadIdRef.current || state.currentThreadId || selectedChatThreadId;
    
    if (!threadId) {
      throw new Error('No active thread to provide feedback for');
    }

    try {

      if (!useStreaming) {
        // Original blocking approach
        const response = await GraphService.provideFeedbackAndContinue(threadId, content);
        
        if (response.run_status === 'user_feedback') {
          const responseMessage = response.assistant_response || response.plan || 'Response generated';   
          const needsApproval = response.response_type === 'replan';
          
          
          return {
            message: responseMessage,
            needsApproval: needsApproval,
            response_type: response.response_type,
            backendMessageId: response.assistant_message_id // Include backend message ID for replan
          };
          
        } else if (response.run_status === 'finished') {
          const finalResponse = response.assistant_response || 'Task completed successfully after feedback.';
          
          let detailedResponse = finalResponse;
          if (response.steps && response.steps.length > 0) {
            detailedResponse += `\n\n**Execution Summary:**\n`;
            detailedResponse += `- Steps executed: ${response.steps.length}\n`;
            if (response.overall_confidence) {
              detailedResponse += `- Overall confidence: ${(response.overall_confidence * 100).toFixed(1)}%\n`;
            }
            if (response.total_time) {
              detailedResponse += `- Total time: ${response.total_time.toFixed(2)}s\n`;
            }
          }
          
          // Do not auto-open panels; allow clicking message card to open
          
          return {
            message: detailedResponse,
            needsApproval: false,
            checkpoint_id: response.checkpoint_id, // Add checkpoint ID for both explorer and visualization messages
            ...(response.steps && response.steps.length > 0 ? { explorerData: response } : {}),
            ...(response.visualizations && response.visualizations.length > 0 ? { visualizations: response.visualizations } : {})
          };
          
        } else if (response.run_status === 'error') {
          throw new Error(response.error || 'An error occurred during execution');
        } else {
          const assistantResponse = response.assistant_response || 'Processing feedback...';
          return {
            message: assistantResponse,
            needsApproval: false
          };
        }
      } else {

        return {
          message: '', // This will be filled by streaming
          needsApproval: false, // This will be determined by streaming status
          isStreaming: true,
          streamingHandler: async (
            streamingMessageId: number,
            updateMessageCallback: (id: number, content: string) => void,
            onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error' | 'tool_call' | 'tool_result' | 'completed_payload' | 'visualizations_ready', eventData?: string) => void
          ) => {
            await resumeStreamingForMessage(threadId, 'feedback', content, streamingMessageId, updateMessageCallback, onStatus);
          }
        };
      }
      
    } catch (error) {
      console.error('Error providing feedback:', error);
      throw error;
    }
  };

  const handleCancel = async (_content: string, message: Message): Promise<string> => {
    
    const threadId = currentThreadIdRef.current || state.currentThreadId || selectedChatThreadId || message.threadId;
    
    if (!threadId) {
      throw new Error('No active thread to cancel');
    }

    try {
      
      await GraphService.cancelExecution(threadId);
      
      return `**Execution Cancelled**\n\nThe task has been cancelled and will not be executed.`;
      
    } catch (error) {
      console.error('Error cancelling execution:', error);
      throw error;
    }
  };

  const handleRetry = async (message: Message): Promise<HandlerResponse | void> => {
    
    const threadId = message.threadId || state.currentThreadId;
    
    if (!threadId) {
      throw new Error('No thread ID available for retry');
    }

    try {
      let response;
      
      if (message.retryAction === 'approve') {
        response = await GraphService.approveAndContinue(threadId);
      } else if (message.retryAction === 'feedback') {
        response = await GraphService.provideFeedbackAndContinue(threadId, 'Retrying previous action');
      } else {
        throw new Error('Unknown retry action');
      }

      if (response.run_status === 'finished') {
        const finalResponse = response.assistant_response || 'Task completed successfully after retry.';
        
        let detailedResponse = finalResponse;
        if (response.steps && response.steps.length > 0) {
          detailedResponse += `\n\n**Execution Summary:**\n`;
          detailedResponse += `- Steps executed: ${response.steps.length}\n`;
          if (response.overall_confidence) {
            detailedResponse += `- Overall confidence: ${(response.overall_confidence * 100).toFixed(1)}%\n`;
          }
          if (response.total_time) {
            detailedResponse += `- Total time: ${response.total_time.toFixed(2)}s\n`;
          }
        }
        

        return {message: detailedResponse, needsApproval: false};
        
      } else if (response.run_status === 'user_feedback') {
        const newPlan = response.assistant_response || response.plan || 'New plan generated after retry - awaiting approval';
        const planMessage = `**Plan after retry:**\n\n${newPlan}\n\n⚠️ **This plan requires your approval before execution.**`;
        
      
        
        return {message: planMessage || '', needsApproval: true};
        
      } else if (response.run_status === 'error') {
        throw new Error(response.error || 'An error occurred during retry');
      }
      
      const fallbackResponse = response.assistant_response || 'Retry completed.';
      
      return {message: fallbackResponse, needsApproval: false};
      
    } catch (error) {
      console.error('Error during retry:', error);
      throw error;
    }
  };

  // Handle thread selection
  const handleThreadSelect = async (threadId: string | null) => {
    if (threadId === selectedChatThreadId) return;

    setLoadingThread(true);
    try {
      setSelectedChatThreadId(threadId);
      currentThreadIdRef.current = threadId;
      
      if (threadId) {
        const thread = await ChatHistoryService.restoreThread(threadId);
        const convertedMessages = convertChatHistoryToMessages(thread.messages || []);
        
        // Set the thread title
        setCurrentThreadTitle(thread.title || 'Untitled Thread');
        
        setThreadId(threadId);
        setExplorerData(null);
        setExplorerOpen(false);
        setVisualizationCharts(null);
        setVisualizationOpen(false);
        
        await restoreDataIfNeeded(convertedMessages, threadId);
        setChatKey(prev => prev + 1);
      } else {
        // Clear thread when null (e.g., after deletion)
        setRestoredMessages([]);
        setCurrentThreadTitle('');
        setChatKey(prev => prev + 1);
        setThreadId(null);
        setExplorerData(null);
        setExplorerOpen(false);
        setVisualizationCharts(null);
        setVisualizationOpen(false);
      }
    } catch (error) {
      console.error('Error selecting thread:', error);
      alert('Failed to load chat thread');
    } finally {
      setLoadingThread(false);
    }
  };

  const handleNewThread = () => {
    setSelectedChatThreadId(null);
    currentThreadIdRef.current = null;
    setRestoredMessages([]);
    setCurrentThreadTitle(''); // Clear thread title for new thread
    setChatKey(prev => prev + 1);
    setThreadId(null);
    setExplorerData(null);
    setExplorerOpen(false);
    setVisualizationCharts(null);
    setVisualizationOpen(false);
  };

  // Handle thread title changes
  const handleTitleChange = async (newTitle: string) => {
    if (!selectedChatThreadId) return;
    
    try {
      // Update the title via API (you'll need to implement this endpoint)
      // await ChatHistoryService.updateThreadTitle(selectedChatThreadId, newTitle);
      setCurrentThreadTitle(newTitle);
    } catch (error) {
      console.error('Failed to update thread title:', error);
      // You might want to show an error message to the user
    }
  };

  return (
    <div className="h-full w-full overflow-hidden">
      {/* Enhanced Sidebar - always visible, expands/collapses */}
      <EnhancedSidebar2
        selectedThreadId={selectedChatThreadId || undefined}
        onThreadSelect={handleThreadSelect}
        onNewThread={handleNewThread}
        onExpandedChange={setSidebarExpanded}
      />

  
      <div className={`h-full min-h-0 flex flex-col transition-[margin-left] duration-300 ease-in-out overflow-hidden ml-0 ${sidebarExpanded ? 'md:ml-82' : 'md:ml-14'}`}>
        <div className="w-full h-full flex flex-col min-h-0">
        
      
          {/* Chat Container */}
          <div className="flex-1 min-h-0">
            <div className="w-full h-full">
              <ChatComponent
                key={`chat-approval-${chatKey}`}
                onSendMessage={handleSendMessage}
                onApprove={handleApprove}
                onFeedback={handleFeedback}
                onCancel={handleCancel}
                onRetry={handleRetry}
                currentThreadId={state.currentThreadId || selectedChatThreadId}
                initialMessages={restoredMessages}
                placeholder="Ask me anything..."
                className="h-full"
                onMessageCreated={handleMessageCreated}
                onMessageUpdated={handleMessageUpdated}
                threadTitle={currentThreadTitle}
                onTitleChange={handleTitleChange}
                sidebarExpanded={sidebarExpanded}
              />
            </div>
          </div>

          <div className="text-center">
            {state.currentThreadId || selectedChatThreadId && (
              <span className="text-xs text-gray-500 mr-4">
                Graph Thread: {state.currentThreadId || selectedChatThreadId}
              </span>
            )}
            {loadingThread && (
              <span className="text-xs text-blue-600 mr-4">
                Loading thread...
              </span>
            )}
          </div>
        </div>
        
        {/* Slide-out Panels (mutually exclusive) */}
        <ExplorerPanel open={explorerOpen && !visualizationOpen} onClose={() => setExplorerOpen(false)} data={explorerData} />
        <VisualizationPanel open={visualizationOpen && !explorerOpen} onClose={() => setVisualizationOpen(false)} charts={visualizationCharts || []} />
      </div>
    </div>
  );
};

export default ChatWithApproval;
