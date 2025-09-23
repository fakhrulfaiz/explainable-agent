import React, { useState } from 'react';
import { ChatComponent, ExplorerPanel } from '../components';
import ChatThreadSelector from '../components/ChatThreadSelector';
import { Message, HandlerResponse } from '../types/chat';
import { GraphService } from '../api/services/graphService';
import { ExplorerService } from '../api/services/explorerService';
import { ChatHistoryService } from '../api/services/chatHistoryService';
import { useUIState } from '../contexts/UIStateContext';

const ChatWithApproval: React.FC = () => {
  // Use the UI state context
  const { state, setExecutionStatus, setThreadId, setLoading, setUseStreaming } = useUIState();
  // Streaming preference from UI state (replaces separate StreamingContext)
  const useStreaming = state.useStreaming;
  React.useEffect(() => {
    // Observe context value updates
    console.log('useStreaming state now:', useStreaming);
  }, [useStreaming]);
  
 // Local state for UI-specific concerns
  const [chatKey, setChatKey] = useState<number>(0); // For resetting chat
  const [selectedChatThreadId, setSelectedChatThreadId] = useState<string | null>(null);
  const [explorerOpen, setExplorerOpen] = useState<boolean>(false);
  const [explorerData, setExplorerData] = useState<any | null>(null);
  const [loadingThread, setLoadingThread] = useState<boolean>(false);
  const [restoredMessages, setRestoredMessages] = useState<Message[]>([]);

  // Streaming connection reference
  const eventSourceRef = React.useRef<EventSource | null>(null);
  
  // Thread ID reference to handle race conditions
  const currentThreadIdRef = React.useRef<string | null>(null);

  const convertChatHistoryToMessages = (chatMessages: any[]): Message[] => {
    return chatMessages.map((msg, index) => ({
      id: Date.now() + index,
      role: msg.sender as 'user' | 'assistant',
      content: msg.content,
      timestamp: new Date(msg.timestamp),
      needsApproval: false,
      threadId: selectedChatThreadId || undefined,
      messageType: (msg.message_type as 'message' | 'explorer') || 'message',
      checkpointId: msg.checkpoint_id
    }));
  };

  const restoreExplorerDataIfNeeded = async (messages: Message[], threadId: string) => {
    const explorerMessages = messages.filter(msg => 
      msg.messageType === 'explorer' && 
      msg.checkpointId && 
      msg.role === 'assistant'
    );

    if (explorerMessages.length > 0) {
      try {
        const explorerDataMap = new Map();
        
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
        
        const updatedMessages = messages.map(msg => {
          if (msg.messageType === 'explorer' && explorerDataMap.has(msg.id)) {
            const explorerData = explorerDataMap.get(msg.id);
            return {
              ...msg,
              metadata: { explorerData }
            };
          }
          return msg;
        });
        
        setRestoredMessages(updatedMessages);
        
        const lastExplorerMessage = explorerMessages[explorerMessages.length - 1];
        if (lastExplorerMessage) {
          const lastUpdatedMessage = updatedMessages.find(msg => msg.id === lastExplorerMessage.id);
          if (lastUpdatedMessage?.metadata?.explorerData) {
            setExplorerData(lastUpdatedMessage.metadata.explorerData);
          }
        }
        
      } catch (error) {
        console.error('Failed to restore explorer data:', error);
      }
    } else {
      setRestoredMessages(messages);
    }
  };

  const handleOpenExplorer = (data: any) => {
    if (data) {
      setExplorerData(data);
      setExplorerOpen(true);
    }
  };

  const handleMessageCreated = async (msg: Message) => {
    // Use the ref to get the most current thread ID, avoiding race conditions
    const threadId = currentThreadIdRef.current || state.currentThreadId || selectedChatThreadId || msg.threadId;
    console.log('ChatWithApproval: handleMessageCreated ->', threadId);
    if (!threadId) {
      console.warn('No thread ID available for message persistence:', msg);
      return;
    }
    try {
      await ChatHistoryService.addMessage({
        thread_id: threadId,
        sender: msg.role,
        content: msg.content,
        message_type: msg.messageType || 'message',
        checkpoint_id: msg.checkpointId || undefined,
        message_id: msg.id || undefined,
        needs_approval: msg.needsApproval || undefined,
        approved: msg.approved || undefined,
        disapproved: msg.disapproved || undefined,
        is_error: msg.isError || undefined,
        is_feedback: msg.isFeedback || undefined,
        has_timed_out: msg.hasTimedOut || undefined,
        can_retry: msg.canRetry || undefined,
        retry_action: msg.retryAction || undefined,
        thread_id_ref: msg.threadId || undefined,
        metadata: msg.metadata || undefined
      });
    } catch (e) {
      console.error('Failed to persist message:', e);
    }
  };

  React.useEffect(() => {
    (window as any).openExplorer = handleOpenExplorer;
    return () => {
      delete (window as any).openExplorer;
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
        title: initialMessage ? `Chat: ${initialMessage}` : 'New Chat',
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
    onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error') => void
  ): Promise<void> => {
    try {
      const startResponse = await GraphService.startStreamingGraph({
        human_request: messageContent,
        thread_id: chatThreadId
      });

      console.log('Started streaming for thread:', startResponse.thread_id);
      setThreadId(startResponse.thread_id);
      eventSourceRef.current = GraphService.streamResponse(
        startResponse.thread_id,
        (data) => {
          if (data.content) {
            updateMessageCallback(streamingMessageId, data.content);
          } else if (data.status) {
            console.log('Stream status (from SSE):', data.status);
            setExecutionStatus(data.status);
            console.log('setExecutionStatus called with:', data.status);
            if (onStatus) {
              onStatus(data.status);
            }
          }
        },
        (error) => {
          console.error('Streaming error:', error);
          setLoading(false);
          throw error;
        },
        () => {
          console.log('Streaming completed');
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
    onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error') => void
  ): Promise<void> => {
    try {
      await GraphService.resumeStreamingGraph({
        thread_id: threadId,
        review_action: reviewAction,
        human_comment: humanComment
      });

      console.log('Resumed streaming for thread:', threadId);

      eventSourceRef.current = GraphService.streamResponse(
        threadId,
        (data) => {
          if (data.content && streamingMessageId && updateMessageCallback) {
            updateMessageCallback(streamingMessageId, data.content);
          } else if (data.status) {
            setExecutionStatus(data.status);
            console.log('setExecutionStatus called with:', data.status);
            if (onStatus) {
              onStatus(data.status);
            }
          }
        },
        (error) => {
          console.error('Resume streaming error:', error);
          setLoading(false);
          throw error;
        },
        () => {
          console.log('Resume streaming completed');
          setLoading(false);
        }
      );

    } catch (error) {
      console.error('Failed to resume streaming:', error);
      setLoading(false);
      throw error;
    }
  };

  const handleSendMessage = async (message: string, _messageHistory: Message[]): Promise<HandlerResponse> => {
    setExplorerData(null);
    setExplorerOpen(false);
    setLoading(true);
    setExecutionStatus('running');
    
    try {
      
      let chatThreadId = selectedChatThreadId;
      console.log('ChatWithApproval: handleSendMessage before createNewChatThread (selectedChatThreadId)', selectedChatThreadId);
      if (!chatThreadId) {
        chatThreadId = await createNewChatThread(message);
        // Immediately update the ref to avoid race conditions with message persistence
        currentThreadIdRef.current = chatThreadId;
        setSelectedChatThreadId(chatThreadId);
        setThreadId(chatThreadId);
      } else {
        // Make sure ref is updated even for existing threads
        currentThreadIdRef.current = chatThreadId;
      }
      // Check for active graph
      const hasActiveGraph = await GraphService.hasActiveGraph(chatThreadId);
      if (hasActiveGraph) {
        throw new Error('There\'s already an active graph execution for this thread. Please wait for it to complete or provide feedback.');
      }

      if (!useStreaming) {
        // Original blocking API call
        const response = await GraphService.startGraph({
          human_request: message,
          thread_id: chatThreadId
        });
        if (response.run_status === 'user_feedback') {
          setExecutionStatus('user_feedback');
          setLoading(false);
          
          const plan = response.plan || response.assistant_response || 'Plan generated - awaiting approval';
          const assistantResponse = `**Plan for your request:**\n\n${plan}\n\n**This plan requires your approval before execution.**`;

          return {
            message: assistantResponse,
            needsApproval: true
          };
        } else if (response.run_status === 'finished') {
          setExecutionStatus('finished');
          setLoading(false);
          
          const assistantResponse = response.assistant_response || 'Task completed successfully.'
          if (response.steps && response.steps.length > 0) {
            // Explorer message will be stored automatically by ChatComponent via onMessageCreated
            setExplorerData(response);
            setExplorerOpen(true);
            return {
              message: assistantResponse,
              explorerData: response
            };
          }
          
          return {
            message: assistantResponse,
            needsApproval: false
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
            onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error') => void
          ) => {
            await startStreamingForMessage(message, streamingMessageId, chatThreadId, updateMessageCallback, onStatus);
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
    console.log('Approval attempt:', { messageId: message.id });
    
    const threadId = state.currentThreadId;
    
    if (!threadId) {
      throw new Error('No active thread to approve');
    }

    try {
      console.log('Approving plan for thread:', threadId);
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
          
          if (selectedChatThreadId) {
            // Message will be stored automatically by ChatComponent via onMessageCreated
            
            if (response.steps && response.steps.length > 0) {
              // Explorer message will be stored automatically by ChatComponent via onMessageCreated
              setExplorerData(response);
              setExplorerOpen(true);
              return {
                message: detailedResponse,
                explorerData: response
              };
            }
          }
          
          return {
            message: detailedResponse,
            needsApproval: false
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
            onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error') => void
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

  const handleFeedback = async (content: string, message: Message): Promise<HandlerResponse> => {
    console.log('Feedback attempt:', { messageId: message.id, feedback: content });
    
    const threadId = state.currentThreadId;
    
    if (!threadId) {
      throw new Error('No active thread to provide feedback for');
    }

    try {
      console.log('Providing feedback for thread:', threadId);

      if (!useStreaming) {
        // Original blocking approach
        const response = await GraphService.provideFeedbackAndContinue(threadId, content);
        
        if (response.run_status === 'user_feedback') {
          const newPlan = response.assistant_response || response.plan || 'Revised plan generated - awaiting approval';
          const revisedResponse = `**Revised Plan:**\n\n${newPlan}\n\n**This revised plan requires your approval before execution.**`;
          
          // User feedback message will be stored automatically by ChatComponent via onMessageCreated
          
          return {
            message: revisedResponse,
            needsApproval: true
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
          
          if (selectedChatThreadId) {
            // Message will be stored automatically by ChatComponent via onMessageCreated
            
            if (response.steps && response.steps.length > 0) {
              // Explorer message will be stored automatically by ChatComponent via onMessageCreated
              setExplorerData(response);
              setExplorerOpen(true);
            }
          }
          
          if (response.steps && response.steps.length > 0) {
            return {
              message: detailedResponse,
              explorerData: response
            };
          }
          
          return {
            message: detailedResponse,
            needsApproval: false
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
            onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error') => void
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
    console.log('Cancel attempt:', { messageId: message.id });
    
    const threadId = state.currentThreadId;
    
    if (!threadId) {
      throw new Error('No active thread to cancel');
    }

    try {
      console.log('Cancelling execution for thread:', threadId);
      
      await GraphService.cancelExecution(threadId);
      
      return `**Execution Cancelled**\n\nThe task has been cancelled and will not be executed.`;
      
    } catch (error) {
      console.error('Error cancelling execution:', error);
      throw error;
    }
  };

  const handleRetry = async (message: Message): Promise<HandlerResponse | void> => {
    console.log('Retry attempt:', { messageId: message.id, retryAction: message.retryAction, threadId: message.threadId });
    
    const threadId = message.threadId || state.currentThreadId;
    
    if (!threadId) {
      throw new Error('No thread ID available for retry');
    }

    try {
      let response;
      
      if (message.retryAction === 'approve') {
        console.log('Retrying approval for thread:', threadId);
        response = await GraphService.approveAndContinue(threadId);
      } else if (message.retryAction === 'feedback') {
        console.log('Retrying feedback for thread:', threadId);
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
      setSelectedChatThreadId(threadId)
      currentThreadIdRef.current = threadId;
      
      if (threadId) {
        const thread = await ChatHistoryService.restoreThread(threadId);
        const convertedMessages = convertChatHistoryToMessages(thread.messages || []);
        
        setThreadId(null);
        setExplorerData(null);
        setExplorerOpen(false);
        
        await restoreExplorerDataIfNeeded(convertedMessages, threadId);
        setChatKey(prev => prev + 1);
      } else {
        setRestoredMessages([]);
        setChatKey(prev => prev + 1);
        setThreadId(null);
        setExplorerData(null);
        setExplorerOpen(false);
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
    setChatKey(prev => prev + 1);
    setThreadId(null);
    setExplorerData(null);
    setExplorerOpen(false);
  };

  return (
    <div style={{ height: '100%', padding: '0 0.5rem', display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto', width: '100%', height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      
        {/* Thread Selector */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex-1">
            <ChatThreadSelector
              selectedThreadId={selectedChatThreadId || undefined}
              onThreadSelect={handleThreadSelect}
              onNewThread={handleNewThread}
            />
          </div>
          <div className="ml-4 flex items-center gap-4 flex-shrink-0">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={useStreaming}
                onChange={(e) => {
                  setUseStreaming(e.target.checked);
                }}
              />
              Streaming {useStreaming ? '(on)' : '(off)'}
            </label>
            <div className="text-xs text-gray-500 w-86 text-right">
              {selectedChatThreadId ? `Thread ID: ${selectedChatThreadId}` : ''}
            </div>
          </div>
        </div>

        {/* Chat Container */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
          <div style={{ backgroundColor: 'white', borderRadius: '0.5rem', boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)', height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
            <div className="flex-1 min-h-0" style={{ overflow: 'hidden' }}>
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
              />
            </div>
          </div>
        </div>


        <div className="mt-4 text-center">
          {state.currentThreadId || selectedChatThreadId && (
            <span className="text-xs text-gray-500 mr-4">
              Graph Thread: {state.currentThreadId || selectedChatThreadId}
            </span>
          )}
          {/* Note: pendingApproval status is now handled in ChatComponent */}
          {state.isLoading && (
            <span className="text-xs text-blue-600 mr-4">
              Processing...
            </span>
          )}
          {loadingThread && (
            <span className="text-xs text-blue-600 mr-4">
              Loading thread...
            </span>
          )}
        </div>
      </div>
      {/* Slide-out Explorer Panel */}
      <ExplorerPanel open={explorerOpen} onClose={() => setExplorerOpen(false)} data={explorerData} />
    </div>
  );
};

export default ChatWithApproval;
