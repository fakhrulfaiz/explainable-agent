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
  const { state, setExecutionStatus, setThreadId, setLoading } = useUIState();
  
  // Local state for UI-specific concerns
  const [chatKey, setChatKey] = useState<number>(0); // For resetting chat
  const [selectedChatThreadId, setSelectedChatThreadId] = useState<string | null>(null);
  const [explorerOpen, setExplorerOpen] = useState<boolean>(false);
  const [explorerData, setExplorerData] = useState<any | null>(null);
  const [loadingThread, setLoadingThread] = useState<boolean>(false);
  const [restoredMessages, setRestoredMessages] = useState<Message[]>([]);

 
  const convertChatHistoryToMessages = (chatMessages: any[]): Message[] => {
    return chatMessages.map((msg, index) => ({
      id: Date.now() + index, // Generate unique IDs
      role: msg.sender as 'user' | 'assistant',
      content: msg.content,
      timestamp: new Date(msg.timestamp),
      needsApproval: false, // Historical messages don't need approval
      threadId: selectedChatThreadId || undefined,
      messageType: (msg.message_type as 'message' | 'explorer') || 'message',
      checkpointId: msg.checkpoint_id
    }));
  };

  const restoreExplorerDataIfNeeded = async (messages: Message[], threadId: string) => {
    // Find ALL explorer messages that need data restoration
    const explorerMessages = messages.filter(msg => 
      msg.messageType === 'explorer' && 
      msg.checkpointId && 
      msg.role === 'assistant'
    );

    if (explorerMessages.length > 0) {
      try {
        // Collect all explorer data first
        const explorerDataMap = new Map();
        
        for (const explorerMessage of explorerMessages) {
          try {
            // Fetch explorer data using the checkpoint_id and provided thread_id
            const explorerData = await ExplorerService.getExplorerData(
              threadId,
              explorerMessage.checkpointId!
            );
            
            if (explorerData) {
              explorerDataMap.set(explorerMessage.id, explorerData);
            }
          } catch (error) {
            console.error('Failed to restore explorer data for checkpoint:', explorerMessage.checkpointId, error);
            // Continue with other messages even if one fails
          }
        }
        
        // Create a completely new messages array with updated explorer data
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
        
        // Update all messages at once with completely new array
        setRestoredMessages(updatedMessages);
        
        // Set the most recent explorer data for the panel
        const lastExplorerMessage = explorerMessages[explorerMessages.length - 1];
        if (lastExplorerMessage) {
          const lastUpdatedMessage = updatedMessages.find(msg => msg.id === lastExplorerMessage.id);
          if (lastUpdatedMessage?.metadata?.explorerData) {
            setExplorerData(lastUpdatedMessage.metadata.explorerData);
          }
        }
        
      } catch (error) {
        console.error('Failed to restore explorer data:', error);
        // Don't show error to user, just log it
      }
    } else {
      // No explorer messages, just set the messages as-is
      setRestoredMessages(messages);
    }
  };

  // Function to handle explorer opening from messages
  const handleOpenExplorer = (data: any) => {
    if (data) {
      setExplorerData(data);
      setExplorerOpen(true);
    }
  };

  // Add to window for global access from Message components
  React.useEffect(() => {
    (window as any).openExplorer = handleOpenExplorer;
    return () => {
      delete (window as any).openExplorer;
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
 
  const storeMessage = async (
    chatThreadId: string, 
    sender: 'user' | 'assistant', 
    content: string, 
    messageType: 'message' | 'explorer' = 'message',
    checkpointId?: string
  ) => {
    try {
      await ChatHistoryService.addMessage({
        thread_id: chatThreadId,
        sender,
        content,
        message_type: messageType,
        checkpoint_id: checkpointId
      });
    } catch (error) {
      console.error('Error storing message:', error);
    }
  };

  const handleSendMessage = async (message: string, _messageHistory: Message[]): Promise<HandlerResponse> => {
    // Clear previous explorer data when starting a new request
    setExplorerData(null);
    setExplorerOpen(false);
    
    // Set loading state
    setLoading(true);
    setExecutionStatus('running');
    
    try {
      // Create or use existing chat thread for history storage
      let chatThreadId = selectedChatThreadId;
      if (!chatThreadId) {
        chatThreadId = await createNewChatThread(message);
        setSelectedChatThreadId(chatThreadId);
      } else {
        await storeMessage(chatThreadId, 'user', message);
      }

      // Check if there's already an active graph execution for this thread
      const hasActiveGraph = await GraphService.hasActiveGraph(chatThreadId);
      if (hasActiveGraph) {
        throw new Error('There\'s already an active graph execution for this thread. Please wait for it to complete or provide feedback.');
      }

      const response = await GraphService.startGraph({
        human_request: message,
        thread_id: chatThreadId
      });

      setThreadId(response.thread_id);

      if (response.run_status === 'user_feedback') {
        setExecutionStatus('user_feedback');
        setLoading(false);
        
        const plan = response.plan || response.assistant_response || 'Plan generated - awaiting approval';
        const assistantResponse = `**Plan for your request:**\n\n${plan}\n\n**This plan requires your approval before execution.**`;
        
        // Store assistant response in chat history
        await storeMessage(chatThreadId, 'assistant', assistantResponse);
        
        return {
          message: assistantResponse,
          needsApproval: true
        };
      } else if (response.run_status === 'finished') {
        // Execution completed without approval needed
        setExecutionStatus('finished');
        setLoading(false);
        
        const assistantResponse = response.assistant_response || 'Task completed successfully.';
        
        // Store assistant response in chat history
        // Always store as regular message for chat history
        await storeMessage(chatThreadId, 'assistant', assistantResponse, 'message');
        
        // If response has steps, also store as explorer type with checkpoint ID
        if (response.steps && response.steps.length > 0) {
          await storeMessage(chatThreadId, 'assistant', assistantResponse, 'explorer', response.thread_id);
        }
        
        // Only show explorer if there are actual steps
        if (response.steps && response.steps.length > 0) {
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
      await storeMessage(chatThreadId, 'assistant', assistantResponse);
      return {
        message: assistantResponse,
        needsApproval: false
      };
    } catch (error) {
      console.error('Error in handleSendMessage:', error);
      throw error;
    }
  };

  const handleApprove = async (_content: string, message: Message): Promise<HandlerResponse> => {
    console.log('Approval attempt:', { messageId: message.id });
    
    // Use current thread if available
    const threadId = state.currentThreadId;
    
    if (!threadId) {
      throw new Error('No active thread to approve');
    }

    try {
      console.log('Approving plan for thread:', threadId);
      setLoading(true);
      setExecutionStatus('running');
      
      const response = await GraphService.approveAndContinue(threadId);
      

      if (response.run_status === 'finished') {
        // Return the final result to be displayed in chat
        const finalResponse = response.assistant_response || 'Task completed successfully.';
        
        // Add step information if available
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
        
        // Store assistant response in chat history
        if (selectedChatThreadId) {
          // Always store as regular message for chat history
          await storeMessage(selectedChatThreadId, 'assistant', detailedResponse, 'message');
          
          // If response has steps, also store as explorer type with checkpoint ID
          if (response.steps && response.steps.length > 0) {
            await storeMessage(selectedChatThreadId, 'assistant', detailedResponse, 'explorer', response.thread_id);
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
        // Store assistant response in chat history
        if (selectedChatThreadId) {
          const messageType = response.steps && response.steps.length > 0 ? 'explorer' : 'message';
          const checkpointId = messageType === 'explorer' ? response.thread_id : undefined;
          await storeMessage(selectedChatThreadId, 'assistant', assistantResponse, messageType, checkpointId);
        }
        return {
          message: assistantResponse,
          needsApproval: false
        };
      }
      
    } catch (error) {
      console.error('Error approving plan:', error);
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
      
      
      const response = await GraphService.provideFeedbackAndContinue(threadId, content);
      
      
      // Note: pendingApproval is now handled locally in ChatComponent
      
      if (response.run_status === 'user_feedback') {
        // New plan generated, need approval again
        const newPlan =  response.assistant_response || response.plan || 'Revised plan generated - awaiting approval';
        
        // Set up pending approval info for the revised plan - we'll update the messageId via callback
        // Note: pendingApproval is now handled locally in ChatComponent
        // Note: pendingApproval is now handled locally in ChatComponent
        const revisedResponse = `**Revised Plan:**\n\n${newPlan}\n\n**This revised plan requires your approval before execution.**`;
        
        // Store feedback and revised plan in chat history
        if (selectedChatThreadId) {
          await storeMessage(selectedChatThreadId, 'user', content); // Store the feedback
          await storeMessage(selectedChatThreadId, 'assistant', revisedResponse); // Store the revised plan
        }
        
        return {
          message: revisedResponse,
          needsApproval: true
        };
        
      } else if (response.run_status === 'finished') {
        // Execution completed after feedback
        const finalResponse = response.assistant_response || 'Task completed successfully after feedback.';
        
        // Add step information if available
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
        
        // Store assistant response in chat history
        if (selectedChatThreadId) {
          // Always store as regular message for chat history
          await storeMessage(selectedChatThreadId, 'assistant', detailedResponse, 'message');
          
          // If response has steps, also store as explorer type with checkpoint ID
          if (response.steps && response.steps.length > 0) {
            await storeMessage(selectedChatThreadId, 'assistant', detailedResponse, 'explorer', response.thread_id);
            setExplorerData(response);
            setExplorerOpen(true);
          }
        }
        
        // Return response object with explorer data if steps are available
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
        // Store assistant response in chat history
        if (selectedChatThreadId) {
          await storeMessage(selectedChatThreadId, 'assistant', assistantResponse);
        }
        return {
          message: assistantResponse,
          needsApproval: false
        };
      }
      
    } catch (error) {
      console.error('Error providing feedback:', error);
      throw error;
    }
  };

  const handleCancel = async (_content: string, message: Message): Promise<string> => {
    console.log('Cancel attempt:', { messageId: message.id });
    
    // Use current thread if available
    const threadId = state.currentThreadId;
    
    if (!threadId) {
      throw new Error('No active thread to cancel');
    }

    try {
      console.log('Cancelling execution for thread:', threadId);
      
      // Cancel the execution
      await GraphService.cancelExecution(threadId);
      
      // Clear pending approval
      // Note: pendingApproval is now handled locally in ChatComponent
      
      return `**Execution Cancelled**\n\nThe task has been cancelled and will not be executed.`;
      
    } catch (error) {
      console.error('Error cancelling execution:', error);
      throw error;
    }
  };

  // Handle retry for timed-out operations
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

      // Clear pending approval since we're retrying
      // Note: pendingApproval is now handled locally in ChatComponent
      
      // Handle the response similar to the original handlers
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
        
        // Store the retry response in chat history
        if (selectedChatThreadId) {
          await storeMessage(selectedChatThreadId, 'assistant', detailedResponse);
        }
        
        return {message: detailedResponse, needsApproval: false};
        
      } else if (response.run_status === 'user_feedback') {
        const newPlan = response.assistant_response || response.plan || 'New plan generated after retry - awaiting approval';
        
        // Note: pendingApproval is now handled locally in ChatComponent
        
        const planMessage = `**Plan after retry:**\n\n${newPlan}\n\n⚠️ **This plan requires your approval before execution.**`;
        
        // Store the retry plan response in chat history
        if (selectedChatThreadId) {
          await storeMessage(selectedChatThreadId, 'assistant', planMessage);
        }
        
        return {message: planMessage || '', needsApproval: true};
        
      } else if (response.run_status === 'error') {
        throw new Error(response.error || 'An error occurred during retry');
      }
      
      const fallbackResponse = response.assistant_response || 'Retry completed.';
      
      // Store the fallback retry response in chat history
      if (selectedChatThreadId) {
        await storeMessage(selectedChatThreadId, 'assistant', fallbackResponse);
      }
      
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
      
      if (threadId) {
        // Load the selected thread and restore messages
        const thread = await ChatHistoryService.restoreThread(threadId);
       
        const convertedMessages = convertChatHistoryToMessages(thread.messages || []);
        
        // Reset current states first
        setThreadId(null);
        // Note: pendingApproval is now handled locally in ChatComponent
        setExplorerData(null);
        setExplorerOpen(false);
        
        // Restore explorer data BEFORE setting messages and triggering re-render
        await restoreExplorerDataIfNeeded(convertedMessages, threadId);
        
        // The restoreExplorerDataIfNeeded function now handles setRestoredMessages internally
        // so we don't need to call it here anymore
        
        setChatKey(prev => prev + 1);
      } else {
        // Clear selection and messages
        setRestoredMessages([]);
        setChatKey(prev => prev + 1);
        
        // Reset current states
        setThreadId(null);
        // Note: pendingApproval is now handled locally in ChatComponent
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

  // Handle creating new thread
  const handleNewThread = () => {
    setSelectedChatThreadId(null);
    setRestoredMessages([]); // Clear restored messages
    setChatKey(prev => prev + 1);
    setThreadId(null);
        // Note: pendingApproval is now handled locally in ChatComponent
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
          <div className="text-xs text-gray-500 ml-4 flex-shrink-0 w-86 text-right">
            {selectedChatThreadId ? `Thread ID: ${selectedChatThreadId}` : ''}
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
                currentThreadId={state.currentThreadId}
                initialMessages={restoredMessages}
                placeholder="Ask me anything..."
                className="h-full"
                renderBelowLastMessage={null}
              />
            </div>
          </div>
        </div>


        <div className="mt-4 text-center">
          {state.currentThreadId && (
            <span className="text-xs text-gray-500 mr-4">
              Graph Thread: {state.currentThreadId}
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
