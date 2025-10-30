import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { Message as MessageType, ChatComponentProps, HandlerResponse } from '../types/chat';
import { useUIState } from '../contexts/UIStateContext';
import Message from './Message';
import FeedbackForm from './FeedbackForm';
import LoadingIndicator from './LoadingIndicator';
import InputForm from './InputForm';
import '../styles/scrollbar.css';


const EphemeralToolIndicator: React.FC<{ 
  steps: Array<{ 
    name: string; 
    id: string; 
    startTime: number; 
    endTime?: number;
    status: 'calling' | 'completed';
  }> 
}> = ({ steps }) => {
  return (
    <div className="bg-gray-50 dark:bg-gray-800 border-l-4 border-gray-300 dark:border-gray-600 p-3 mb-2 rounded-r-lg">
      <div className="space-y-2">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-center gap-2 text-sm">
            {step.status === 'completed' ? (
              <div className="w-3 h-3 bg-gray-800 dark:bg-gray-200 rounded-full flex-shrink-0 flex items-center justify-center">
                <span className="text-white dark:text-gray-800 text-xs">✓</span>
              </div>
            ) : (
              <div className="w-3 h-3 border-2 border-gray-600 dark:border-gray-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
            )}
            <span className={`font-medium ${step.status === 'completed' ? 'text-gray-800 dark:text-gray-200' : 'text-gray-700 dark:text-gray-300'}`}>
              {step.status === 'completed' 
                ? `Step ${index + 1}: ${step.name || 'Unknown Tool'} (completed)` 
                : `Step ${index + 1}: ${step.name || 'Unknown Tool'}...`
              }
            </span>
            <span className={`text-xs ${step.status === 'completed' ? 'text-gray-600 dark:text-gray-400' : 'text-gray-500 dark:text-gray-500'}`}>
              {step.status === 'completed' 
                ? `${Math.max(1, Math.floor((step.endTime! - step.startTime) / 1000))}s`
                : `${Math.floor((Date.now() - step.startTime) / 1000)}s`
              }
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

const ChatComponent: React.FC<ChatComponentProps> = ({ 
  onSendMessage, 
  onApprove, 
  onFeedback,
  onCancel,
  onRetry,
  currentThreadId,
  initialMessages = [],
  className = "",
  placeholder = "Type your message...",
  disabled = false,
  onMessageCreated
}) => {
  // Use UI state context for loading and execution state
  const { state, setExecutionStatus, setLoading } = useUIState();
  
  const [messages, setMessages] = useState<MessageType[]>(initialMessages);
  const [inputValue, setInputValue] = useState<string>('');
  const [pendingApproval, setPendingApproval] = useState<number | null>(null);
  const [showFeedbackForm, setShowFeedbackForm] = useState<boolean>(false);
  const [feedbackText, setFeedbackText] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // Streaming UI state
  const [streamingActive, setStreamingActive] = useState<boolean>(false);
  
  // Enhanced input state
  const [usePlanning, setUsePlanning] = useState<boolean>(false);
  const [useExplainer, setUseExplainer] = useState<boolean>(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  
  // Tool call state for ephemeral indicators - now tracks step history
  const [toolStepHistory, setToolStepHistory] = useState<{
    messageId: number;
    steps: Array<{ 
      name: string; 
      id: string; 
      startTime: number; 
      endTime?: number;
      status: 'calling' | 'completed';
    }>;
  } | null>(null);
  
  // Use shared state from context
  const isLoading = state.isLoading;
  const contextThreadId = state.currentThreadId;
  const showApprovalButtons = pendingApproval !== null && state.executionStatus === 'user_feedback';
  const messagesRef = useRef<MessageType[]>([]);



  const scrollToBottom = (): void => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (messages.length > 0) {
      scrollToBottom();
    }
  }, [messages]);

  // Mirror messages into a ref for post-await access
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);


  // Auto-set pendingApproval when messages change and there's no current pending approval
  useEffect(() => {
    if (!pendingApproval && messages.length > 0) {
      const messageNeedingApproval = messages.find(m => m.needsApproval);
      if (messageNeedingApproval) {
        setPendingApproval(messageNeedingApproval.id);
      }
    }
  }, [messages, pendingApproval]);


  // Memoize initialMessages to prevent unnecessary re-renders
  const memoizedInitialMessages = useMemo(() => initialMessages, [
    initialMessages.length,
    initialMessages.map(m => m.id).join(','),
    initialMessages.map(m => m.content).join(',')
  ]);

  // Update messages when initialMessages prop changes
  useEffect(() => {
    setMessages(memoizedInitialMessages);
  }, [memoizedInitialMessages]);

  // Separate method for creating explorer messages (as suggested)
  const createExplorerMessage = useCallback((response: HandlerResponse): void => {
    if (!response.explorerData) return;
    
    const explorerMessage: MessageType = {
      id: Date.now() + Math.floor(Math.random() * 1000), // Ensure unique ID with random component
      role: 'assistant',
      content: response.message,
      timestamp: new Date(),
      messageType: 'explorer',
      checkpointId: response.explorerData.checkpoint_id, 
      metadata: { explorerData: response.explorerData },
      threadId: contextThreadId || currentThreadId || undefined
    };
    
    // Add explorer message after a short delay to ensure proper ordering
    setTimeout(() => {
      setMessages(prev => [...prev, explorerMessage]);
      if (typeof onMessageCreated === 'function') {
        onMessageCreated(explorerMessage);
      }
    }, 50);
  }, [contextThreadId, currentThreadId, onMessageCreated]);

  // Helper function to handle response and create special messages if needed
  const handleResponse = useCallback((response: HandlerResponse): string => {
    if (response.explorerData) {
      createExplorerMessage(response);
    }
    if (response.visualizations && response.visualizations.length > 0) {
      const vizMessage: MessageType = {
        id: Date.now() + Math.floor(Math.random() * 1000) + 10000, // Ensure unique ID with different random component
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
        messageType: 'visualization',
        checkpointId: response.checkpoint_id, // Add checkpoint ID for visualization messages
        metadata: { visualizations: response.visualizations },
        threadId: contextThreadId || currentThreadId || undefined
      } as any;
      setTimeout(() => {
        setMessages(prev => [...prev, vizMessage]);
        if (typeof onMessageCreated === 'function') {
          onMessageCreated(vizMessage);
        }
      }, 50);
    }
    return response.message;
  }, [createExplorerMessage, contextThreadId, currentThreadId, onMessageCreated]);


// Helper function to handle streaming errors
const handleStreamingError = useCallback((
  streamErr: Error,
  streamingMsgId: number
) => {
  setMessages(prev => prev.map(m => 
    m.id === streamingMsgId
      ? { ...m, content: `Error: ${streamErr.message || 'Streaming failed'}`, isError: true, isStreaming: false }
      : m
  ));
}, []);

// Helper function to check if error is timeout
const isTimeoutError = useCallback((error: Error) => {
  const errorMsg = error.message || 'Something went wrong';
  return errorMsg.includes('timeout') || 
         errorMsg.includes('30000ms exceeded') || 
         errorMsg.includes('Request timed out') ||
         errorMsg.includes('ECONNABORTED') ||
         (error as any)?.code === 'ECONNABORTED';
}, []);

// Helper function to update message properties
const updateMessage = useCallback((
  messageId: number,
  updates: Partial<MessageType>
) => {
  setMessages(prev => prev.map(m => 
    m.id === messageId ? { ...m, ...updates } : m
  ));
}, []);

// Helper function to handle tool events
const handleToolEvents = useCallback((
  status: string,
  eventData: string | undefined,
  streamingMsgId: number
) => {
  // Handle tool call start - show temporary indicator
  if (status === 'tool_call' && eventData) {
    const toolData = JSON.parse(eventData);
    setToolStepHistory(prev => {
      const newStep = {
        name: toolData.tool_name || 'Unknown Tool',
        id: toolData.tool_id,
        startTime: Date.now(),
        status: 'calling' as const
      };
      return {
        messageId: streamingMsgId,
        steps: [
          ...(prev?.messageId === streamingMsgId ? prev.steps : []),
          newStep
        ]
      };
    });
  }
  
  // Handle tool result - remove the temporary indicator
  if (status === 'tool_result' && eventData) {
    const resultData = JSON.parse(eventData);
    setToolStepHistory(prev => {
      if (!prev || prev.messageId !== streamingMsgId) return prev;
      
      const updatedSteps = prev.steps.map(step => 
        step.id === resultData.tool_call_id 
          ? { ...step, status: 'completed' as const, endTime: Date.now() }
          : step
      );
      return { ...prev, steps: updatedSteps };
    });
  }
}, []);

const updateMessageCallback = useCallback(
  (messageId: number, appendContent: string): void => {
    let parsedContent: string | null = null;
    try {
      const parsed = JSON.parse(appendContent);
      if (parsed && typeof parsed === "object") {
        if (parsed.id && parsed.role && parsed.messageType) {
          const newMessage: MessageType = {
            id: parsed.id,
            role: parsed.role as 'assistant' | 'user',
            content: parsed.content,
            timestamp: new Date(parsed.timestamp),
            messageType: parsed.messageType,
            checkpointId: parsed.checkpointId,
            metadata: parsed.metadata,
            threadId: parsed.threadId
          };
          
          setMessages(prev => [...prev, newMessage]);
          if (typeof onMessageCreated === 'function') {
            onMessageCreated(newMessage);
          }
          return;
        }
        if ("content" in parsed) {
          parsedContent = parsed.content;
        }

      }
    } catch {
      
    }

    const finalAppend = parsedContent ?? appendContent;
    setMessages(prev =>
        prev.map(m => {
          if (m.id === messageId) {
            return { ...m, content: (m.content || "") + finalAppend };
          }
          return m;
        })
      );
    
  },
  []
);


  const handleSend = async (): Promise<void> => {
    if (!inputValue.trim() || isLoading || disabled || streamingActive) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setPendingApproval(null);

    const newUserMessage: MessageType = {
      id: Date.now(),
      role: 'user',
      content: userMessage,
      timestamp: new Date(),
      threadId: contextThreadId || currentThreadId || undefined,
      metadata: {
        attachedFiles: attachedFiles
      }
    };

    setMessages(prev => [...prev, newUserMessage]);
  if (typeof onMessageCreated === 'function') {
    onMessageCreated(newUserMessage);
  }

    try {
      const response = await onSendMessage(userMessage, messages, { usePlanning, useExplainer, attachedFiles });
      if (response.isStreaming && response.streamingHandler) {
        
        const streamingMsgId = Date.now() + 1;
        const streamingMessage: MessageType = {
          id: streamingMsgId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          threadId: contextThreadId || currentThreadId || undefined,
          isStreaming: true
        } as any;
        setMessages(prev => [...prev, streamingMessage]);
        setStreamingActive(true);

        try {
          await response.streamingHandler(streamingMsgId, updateMessageCallback, (status, eventData, responseType) => {
            if (!status) return;            
            
            // Handle tool events
            handleToolEvents(status, eventData, streamingMsgId);
            
            if (status === 'finished' || status === 'user_feedback') {
              setToolStepHistory(null);
              
              setMessages(prev => prev.map(m => 
                m.id === streamingMsgId
                  ? { 
                      ...m, 
                      isStreaming: status !== 'finished', 
                      needsApproval: status === 'user_feedback' && (responseType === 'replan' || responseType === undefined)
                    }
                  : m
              ));
              
              if (status === 'user_feedback' && (responseType === 'replan' || responseType === undefined)) {
                setPendingApproval(streamingMsgId);
              }
            }

            if (status === 'completed_payload') {
              console.log("🔧 FRONTEND: Status event payload:", status);
            }
            else if (status === 'visualizations_ready') {
              console.log("🔧 FRONTEND: Status event payload:", status);
            }
            
            
          });               
        } catch (streamErr) {
          handleStreamingError(streamErr as Error, streamingMsgId);
        } finally {
          setStreamingActive(false);
        }
      } else {
      const messageContent = handleResponse(response);
      const assistantMessage: MessageType = {
        id: response.backendMessageId || Date.now() + 1, // Use backend ID if available
        role: 'assistant',
        content: messageContent,
        timestamp: new Date(),
        needsApproval: response.needsApproval,
        threadId: contextThreadId || currentThreadId || undefined
      };
        setMessages(prev => [...prev, assistantMessage]);
        if (typeof onMessageCreated === 'function') {
          onMessageCreated(assistantMessage);
        }
      if (response.needsApproval) {
        setPendingApproval(assistantMessage.id);
        setShowFeedbackForm(false);
        setFeedbackText('');
      } else {
        setPendingApproval(null);
        }
      }

    } catch (error) {
      // Add error message
      const errorMessage: MessageType = {
        id: Date.now() + 1,
        role: 'assistant',
        content: `Error: ${(error as Error).message || 'Something went wrong'}`,
        timestamp: new Date(),
        isError: true
      };

      setMessages(prev => [...prev, errorMessage]);
      if (typeof onMessageCreated === 'function') {
        onMessageCreated(errorMessage);
      }
    } 
  };

  const handleApprove = async (messageId: number): Promise<void> => {
    const message = messages.find(m => m.id === messageId);
    
    if (!message) {
      return;
    }
    
    
    if (!message.needsApproval) {
      return;
    }
    
    setShowFeedbackForm(false);
    setFeedbackText('');
    setPendingApproval(null);
    setExecutionStatus('running');
    setLoading(true);
    
    
    updateMessage(messageId, { approved: true, needsApproval: false });

    try {
      
      if (onApprove) {
        const result = await onApprove(message.content, message);
        if (result) {
          if ((result as HandlerResponse).isStreaming && (result as HandlerResponse).streamingHandler) {
            const streamingMsgId = Date.now() + 1;
            const streamingMessage: MessageType = {
              id: streamingMsgId,
              role: 'assistant',
              content: '',
              timestamp: new Date(),
              threadId: message.threadId || contextThreadId || currentThreadId || undefined,
              isStreaming: true
            } as any;
            setMessages(prev => [...prev, streamingMessage]);
            setStreamingActive(true);
            try {
              await (result as HandlerResponse).streamingHandler!(streamingMsgId, updateMessageCallback, (status, eventData, responseType) => {
                if (!status) return;
                
                
                if (status === 'tool_call' && eventData) {
                  const toolData = JSON.parse(eventData);
                  setToolStepHistory(prev => {
                    const newStep = {
                      name: toolData.tool_name || 'Unknown Tool',
                      id: toolData.tool_id,
                      startTime: Date.now(),
                      status: 'calling' as const
                    };
                    return {
                      messageId: streamingMsgId,
                      steps: [
                        ...(prev?.messageId === streamingMsgId ? prev.steps : []),
                        newStep
                      ]
                    };
                  });
                }
                
                
                if (status === 'tool_result' && eventData) {
                  const resultData = JSON.parse(eventData);
                  setToolStepHistory(prev => {
                    if (!prev || prev.messageId !== streamingMsgId) return prev;
                    
                    const updatedSteps = prev.steps.map(step => 
                      step.id === resultData.tool_call_id 
                        ? { ...step, status: 'completed' as const, endTime: Date.now() }
                        : step
                    );
                    return { ...prev, steps: updatedSteps };
                  });
                }
                
                
                if (status === 'finished' || status === 'user_feedback') {
                  setToolStepHistory(null);
                  
                  setMessages(prev => prev.map(m => 
                    m.id === streamingMsgId
                      ? { 
                          ...m, 
                          isStreaming: status !== 'finished', 
                          needsApproval: status === 'user_feedback' && (responseType === 'replan' || responseType === undefined)
                        }
                      : m
                  ));
                  
                  if (status === 'user_feedback' && (responseType === 'replan' || responseType === undefined)) {
                    setPendingApproval(streamingMsgId);
                  }
                }
              });
            } catch (streamErr) {
              setMessages(prev => prev.map(m => 
                m.id === streamingMsgId
                  ? { ...m, content: `Error: ${(streamErr as Error).message || 'Streaming failed'}`, isError: true, isStreaming: false }
                  : m
              ));
              if (typeof onMessageCreated === 'function') {
                const finalMsg = messagesRef.current.find(m => m.id === streamingMsgId);
                if (finalMsg) onMessageCreated(finalMsg);
              }
            } finally {
              setStreamingActive(false);
            }
          } else {
          const messageContent = handleResponse(result as HandlerResponse);
          const resultMessage: MessageType = {
            id: Date.now() + 1,
            role: 'assistant',
            content: messageContent,
            timestamp: new Date()
          };
          setMessages(prev => [...prev, resultMessage]);
            if (typeof onMessageCreated === 'function') {
              onMessageCreated(resultMessage);
            }
          }
        }
      }
    } catch (error) {
      const isTimeout = isTimeoutError(error as Error);
      
      if (isTimeout) {
        
        setMessages(prev => prev.map(m => 
          m.id === messageId 
            ? { 
                ...m, 
                approved: false,
                needsApproval: true, // Restore needsApproval since it failed
                hasTimedOut: true, 
                canRetry: true, 
                retryAction: 'approve' as const,
                threadId: message.threadId
              }
            : m
        ));
      } else {
        
        updateMessage(messageId, { approved: false, needsApproval: true });
        
        const errorMessage: MessageType = {
          id: Date.now() + 1,
          role: 'assistant',
          content: `Error during approval: ${(error as Error).message || 'Something went wrong'}`,
          timestamp: new Date(),
          isError: true
        };

        setMessages(prev => [...prev, errorMessage]);
      }
    }
    finally {
      setLoading(false);
      }
  };

  const handleFeedback = async (messageId: number): Promise<void> => {
    const message = messages.find(m => m.id === messageId);
    if (!message) return;
    
    // Only allow providing feedback for messages that need approval
    if (!message.needsApproval) {
      return;
    }

    setShowFeedbackForm(false);
    setFeedbackText('');

    // DON'T clear needsApproval yet - keep it so user can still approve after clarification
    // It will be cleared only if a new plan is generated

    try {
      // Call parent handler
      if (onFeedback) {
        const result = await onFeedback(message.content, message);
        if (result) {
          if ((result as HandlerResponse).isStreaming && (result as HandlerResponse).streamingHandler) {
            const streamingMsgId = Date.now() + 1;
            const streamingMessage: MessageType = {
              id: streamingMsgId,
              role: 'assistant',
              content: '',
              timestamp: new Date(),
              threadId: message.threadId || contextThreadId || currentThreadId || undefined,
              isStreaming: true
            } as any;
            setMessages(prev => [...prev, streamingMessage]);
            setStreamingActive(true);
            try {
              await (result as HandlerResponse).streamingHandler!(streamingMsgId, updateMessageCallback, (status, eventData, responseType) => {
                if (!status) return;
                
                // Handle tool events
                handleToolEvents(status, eventData, streamingMsgId);
                
                // Clear all tool indicators when streaming finishes
                if (status === 'finished' || status === 'user_feedback') {
                  setToolStepHistory(null);
                  
                  setMessages(prev => prev.map(m => {
                    if (m.id === streamingMsgId) {
                      // Update the streaming message
                      // Only needs approval if response_type is 'replan'
                      const needsApproval = status === 'user_feedback' && responseType === 'replan';
                      return { 
                        ...m, 
                        isStreaming: status !== 'finished', 
                        needsApproval: needsApproval
                      };
                    }
                    // If new plan generated (response_type === 'replan'), clear old plan's needsApproval
                    if (status === 'user_feedback' && responseType === 'replan' && m.id === messageId) {
                      return { ...m, needsApproval: false };
                    }
                    return m;
                  }));
                  
                  if (status === 'user_feedback' && responseType === 'replan') {
                    setPendingApproval(streamingMsgId);
                  }
                  // Note: For clarifications, pendingApproval will be auto-set by useEffect
                }
              });
            } catch (streamErr) {
              setMessages(prev => prev.map(m => 
                m.id === streamingMsgId
                  ? { ...m, content: `Error: ${(streamErr as Error).message || 'Streaming failed'}`, isError: true, isStreaming: false }
                  : m
              ));
              if (typeof onMessageCreated === 'function') {
                const finalMsg = messagesRef.current.find(m => m.id === streamingMsgId);
                if (finalMsg) onMessageCreated(finalMsg);
              }
            } finally {
              setStreamingActive(false);
            }
          } else {
          const messageContent = handleResponse(result as HandlerResponse);
          const needsApproval = (result as HandlerResponse).needsApproval || false;
          const backendId = (result as HandlerResponse).backendMessageId;
          const tempId = Date.now() + 1;
          const finalId = backendId || tempId;
          const resultMessage: MessageType = {
            id: finalId,  // Use backend ID if available
            role: 'assistant',
            content: messageContent,
            timestamp: new Date(),
            needsApproval: needsApproval
          };
          
          // Only clear old plan's needsApproval if this is a NEW plan (replan), not a clarification
          if (needsApproval && (result as HandlerResponse).response_type === 'replan') {
            setMessages(prev => prev.map(m => 
              m.id === messageId 
                ? { ...m, needsApproval: false }
                : m
            ));
          }
          
          setMessages(prev => [...prev, resultMessage]);
          if (typeof onMessageCreated === 'function') {
            const finalMsg = messagesRef.current.find(m => m.id === Date.now() + 1);
            if (finalMsg) onMessageCreated(finalMsg);
          }
          if (needsApproval) {
            setPendingApproval(resultMessage.id);
          }
          }
        }
      }
    } catch (error) {
      const isTimeout = isTimeoutError(error as Error);
      
      if (isTimeout) {
        // Mark the message as timed out and retryable
        setMessages(prev => prev.map(m => 
          m.id === messageId 
            ? { 
                ...m, 
                disapproved: false, 
                hasTimedOut: true, 
                canRetry: true, 
                retryAction: 'feedback' as const,
                threadId: message.threadId
              }
            : m
        ));
      } else {
        // Add error message for non-timeout errors
        const errorMessage: MessageType = {
          id: Date.now() + 1,
          role: 'assistant',
          content: `Error during feedback: ${(error as Error).message || 'Something went wrong'}`,
          timestamp: new Date(),
          isError: true
        };

        setMessages(prev => [...prev, errorMessage]);
      }
    } finally {
      setLoading(false);
      }
  };

  const handleSendFeedback = async (): Promise<void> => {
    if (!feedbackText.trim() || !pendingApproval ) return;

    const message = messages.find(m => m.id === pendingApproval);
    if (!message) return;

    // Add feedback as a user message
    const feedbackMessage: MessageType = {
      id: Date.now(),
      role: 'user',
      content: feedbackText.trim(),
      timestamp: new Date(),
      isFeedback: true
    };

    setMessages(prev => [...prev, feedbackMessage]);
    if (typeof onMessageCreated === 'function') {
      const finalMsg = messagesRef.current.find(m => m.id === Date.now());
      if (finalMsg) onMessageCreated(finalMsg);
    }
    setFeedbackText('');
    setShowFeedbackForm(false);

    // DON'T clear needsApproval here - it will be handled by the feedback response
    // The original message should keep needsApproval: true until a new plan is generated

    try {
      // Use the feedback handler instead of sending a new message
      if (onFeedback) {
        const result = await onFeedback(feedbackText.trim(), message);
  
        if (result) {
          if ((result as HandlerResponse).isStreaming && (result as HandlerResponse).streamingHandler) {
            const streamingMsgId = Date.now() + 1;
            const streamingMessage: MessageType = {
              id: streamingMsgId,
              role: 'assistant',
              content: '',
              timestamp: new Date(),
              threadId: message.threadId || contextThreadId || currentThreadId || undefined,
              isStreaming: true
            } as any;
            setMessages(prev => [...prev, streamingMessage]);
            setStreamingActive(true);
            try {
              await (result as HandlerResponse).streamingHandler!(streamingMsgId, updateMessageCallback, (status, eventData, responseType) => {
                if (!status) return;
                
                // Handle tool events
                handleToolEvents(status, eventData, streamingMsgId);
                
                // Clear all tool indicators when streaming finishes
                if (status === 'finished' || status === 'user_feedback') {
                  setToolStepHistory(null);
                  
                  setMessages(prev => prev.map(m => {
                    if (m.id === streamingMsgId) {
                      // Update the streaming message
                      // Only needs approval if response_type is 'replan'
                      const needsApproval = status === 'user_feedback' && responseType === 'replan';
                      return { 
                        ...m, 
                        isStreaming: status !== 'finished', 
                        needsApproval: needsApproval
                      };
                    }
                    // If new plan generated (response_type === 'replan'), clear old plan's needsApproval
                    if (status === 'user_feedback' && responseType === 'replan' && m.id === message.id) {
                      return { ...m, needsApproval: false };
                    }
                    return m;
                  }));
                  
                  if (status === 'user_feedback' && responseType === 'replan') {
                    setPendingApproval(streamingMsgId);
                  }
                  // Note: For clarifications, pendingApproval will be auto-set by useEffect
                }
                
                if (typeof onMessageCreated === 'function') {
                  const finalMsg = messagesRef.current.find(m => m.id === streamingMsgId);
                  if (finalMsg) onMessageCreated(finalMsg);
                }
              });
            } catch (streamErr) {
              setMessages(prev => prev.map(m => 
                m.id === streamingMsgId
                  ? { ...m, content: `Error: ${(streamErr as Error).message || 'Streaming failed'}`, isError: true, isStreaming: false }
                  : m
              ));
              if (typeof onMessageCreated === 'function') {
                const finalMsg = messagesRef.current.find(m => m.id === streamingMsgId);
                if (finalMsg) onMessageCreated(finalMsg);
              }
            } finally {
              setStreamingActive(false);
            }
    } else {
          const messageContent = handleResponse(result as HandlerResponse);
          // Use the needsApproval flag from the response instead of parsing content
          const needsApproval = (result as HandlerResponse).needsApproval || false;
          const resultMessage: MessageType = {
            id: Date.now() + 1,
            role: 'assistant',
            content: messageContent,
            timestamp: new Date(),
            needsApproval: needsApproval
          };
          
          // If a new plan is generated, clear the old plan's needsApproval flag
          if (needsApproval) {
            setMessages(prev => prev.map(m => 
              m.id === message.id 
                ? { ...m, needsApproval: false }
                : m
            ));
          }
          
          setMessages(prev => [...prev, resultMessage]);
          if (typeof onMessageCreated === 'function') {
            const finalMsg = messagesRef.current.find(m => m.id === Date.now() + 1);
            if (finalMsg) onMessageCreated(finalMsg);
          }
          if (needsApproval) {
            setPendingApproval(resultMessage.id);
          }
          // Note: For clarifications, pendingApproval will be auto-set by useEffect
          }
        }
      }
    } catch (error) {
      const isTimeout = isTimeoutError(error as Error);
      
      if (isTimeout) {
        // Mark the message as timed out and retryable
        setMessages(prev => prev.map(m => 
          m.id === message.id 
            ? { 
                ...m, 
                hasTimedOut: true, 
                canRetry: true, 
                retryAction: 'feedback' as const,
                threadId: message.threadId
              }
            : m
        ));
      } else {
        // Add error message for non-timeout errors
        const errorMessage: MessageType = {
          id: Date.now() + 1,
          role: 'assistant',
          content: `Error during feedback: ${(error as Error).message || 'Something went wrong'}`,
          timestamp: new Date(),
          isError: true
        };

        setMessages(prev => [...prev, errorMessage]);
      }
    } finally {
      setLoading(false);
      }
  };

  const handleCancel = async (messageId: number): Promise<void> => {
    // If messageId is 0, find the latest message that needs approval
    let message;
    if (messageId === 0) {
      message = messages.find(m => m.needsApproval === true);
    } else {
      message = messages.find(m => m.id === messageId);
    }
    
    if (!message) {
      return;
    }
    
    // Only allow cancelling messages that need approval
    if (!message.needsApproval) {
      console.warn('Attempted to cancel a message that does not need approval:', messageId);
      return;
    }
    
    setShowFeedbackForm(false);
    setFeedbackText('');
    setPendingApproval(null);
    setExecutionStatus('running');
    setLoading(true);

    // Update message to show it's cancelled
    updateMessage(message.id, { disapproved: true, needsApproval: false });

    try {
      // Call parent cancel handler
      if (onCancel) {
        const result = await onCancel(message.content, message);
        
        // If the cancel handler returns a result, add it as a new message
        if (result) {
          const resultMessage: MessageType = {
            id: Date.now() + 1,
            role: 'assistant',
            content: result,
            timestamp: new Date(),
            needsApproval: false // Cancellation messages don't need approval
          };
          
          setMessages(prev => [...prev, resultMessage]);
          if (typeof onMessageCreated === 'function') {
            const finalMsg = messagesRef.current.find(m => m.id === Date.now() + 1);
            if (finalMsg) onMessageCreated(finalMsg);
          }
        }
      }
    } catch (error) {
      // Add error message if cancellation fails
      const errorMessage: MessageType = {
        id: Date.now() + 1,
        role: 'assistant',
        content: `Error during cancellation: ${(error as Error).message || 'Something went wrong'}`,
        timestamp: new Date(),
        isError: true
      };

      setMessages(prev => [...prev, errorMessage]);
      if (typeof onMessageCreated === 'function') {
        const finalMsg = messagesRef.current.find(m => m.id === Date.now() + 1);
        if (finalMsg) onMessageCreated(finalMsg);
      }
    } finally {
      setLoading(false);
      }
  };

  // const clearChat = (): void => {
  //   setMessages([]);
  //   setShowFeedbackForm(false);
  //   setFeedbackText('');
  //   inputRef.current?.focus();
  // };

  const handleRetry = async (messageId: number): Promise<void> => {
    const message = messages.find(m => m.id === messageId);
    if (!message || !message.canRetry || !message.retryAction) {
      console.log('Retry blocked:', { message, canRetry: message?.canRetry, retryAction: message?.retryAction });
      return;
    }

    console.log('Starting retry for message:', messageId, 'action:', message.retryAction);

    // Clear the timeout state and restore the message to its pre-timeout state
    setMessages(prev => prev.map(m => 
      m.id === messageId 
        ? { 
            ...m, 
            hasTimedOut: false, 
            canRetry: false, 
            retryAction: undefined 
          }
        : m
    ));

    try {
      // Call the parent's retry handler if available
      if (onRetry) {
        const result = await onRetry(message);
        
        // If the retry handler returns a result, add it as a new message
        if (result) {
          // Handle response (could be string or HandlerResponse)
          const messageContent = handleResponse(result);
          
          const resultMessage: MessageType = {
            id: Date.now() + 1,
            role: 'assistant',
            content: messageContent,
            timestamp: new Date(),
            threadId: contextThreadId || currentThreadId || undefined
          };
          
          setMessages(prev => [...prev, resultMessage]);
          if (typeof onMessageCreated === 'function') {
            const finalMsg = messagesRef.current.find(m => m.id === Date.now() + 1);
            if (finalMsg) onMessageCreated(finalMsg);
          }
        }
      } else {
        // Fallback to local retry logic if no parent handler
        if (message.retryAction === 'approve') {
          await handleApprove(messageId);
        } else if (message.retryAction === 'feedback') {
          await handleFeedback(messageId);
        }
      }
    } catch (error) {
      const isTimeout = isTimeoutError(error as Error);
      
      // If retry fails, mark the message as having a timeout error again
      setMessages(prev => prev.map(m => 
        m.id === messageId 
          ? { 
              ...m, 
              hasTimedOut: true, 
              canRetry: true,
              retryAction: message.retryAction // Preserve the original retry action
            }
          : m
      ));
      console.error('Retry failed:', error);
      
      // Also show the error message if it's not a timeout
      if (!isTimeout) {
        const errorMessage: MessageType = {
          id: Date.now() + 1,
          role: 'assistant',
          content: `Retry failed: ${(error as Error).message || 'Something went wrong'}`,
          timestamp: new Date(),
          isError: true
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    } finally {
      setLoading(false);
      }
    // Note: Loading state cleanup is handled by the parent component
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Enhanced input handlers
  const handleFilesChange = (files: File[]): void => {
    setAttachedFiles(files);
  };

  const handlePlanningToggle = (enabled: boolean): void => {
    setUsePlanning(enabled);
  };

  const handleExplainerToggle = (enabled: boolean): void => {
    setUseExplainer(enabled);
  };

  return (
    <div 
      className={`relative flex flex-col h-full min-h-0 ${className}`}
    >
      {/* Messages - scrollable area with padding for fixed input */}
      <div 
        className="flex-1 space-y-4 min-h-0 pb-40 overflow-y-auto slim-scroll pt-32"
      >
        <div className="max-w-3xl mx-auto px-4">
        {messages.map((message) => (
            <React.Fragment key={message.id}>
              <Message
                message={message}
                onRetry={handleRetry}
              />
              
          {/* Inline approval controls under the message that needs approval */}
          {message.needsApproval && message.id === pendingApproval && showApprovalButtons && (
            <div className="mt-0 mb-3 flex gap-2 justify-end max-w-3xl">
              <button
                onClick={() => setShowFeedbackForm(true)}
                className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 dark:bg-white text-white dark:text-neutral-700 rounded-lg hover:bg-gray-700 dark:hover:bg-neutral-400 transition-colors text-sm"
              >
                Send Feedback
              </button>
              <button
                onClick={() => pendingApproval && handleApprove(pendingApproval)}
                className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
              >
                <ThumbsUp className="w-4 h-4" />
                Approve
              </button>
              <button
                onClick={() => pendingApproval && handleCancel(pendingApproval)}
                className="flex items-center gap-1 px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
              >
                <ThumbsDown className="w-4 h-4" />
                Cancel
              </button>
            </div>
          )}

              {(() => {
                const shouldShow = message.isStreaming && 
                                 toolStepHistory?.messageId === message.id && 
                                 toolStepHistory.steps.length > 0;
                return shouldShow && (
                  <EphemeralToolIndicator steps={toolStepHistory.steps} />
                );
              })()}
            </React.Fragment>
          ))}

        {/* Loading indicator */}
        { isLoading && (
          <LoadingIndicator 
            activeTools={toolStepHistory?.steps.filter(s => s.status === 'calling').map(s => s.name)} 
          />
        )}
        <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Fixed Input Area */}
      <div className={`absolute left-0 right-0 z-10 transition-all duration-500 ease-in-out ${
        messages.length === 0 
          ? 'top-1/2 transform -translate-y-1/2 flex items-center justify-center' 
          : 'bottom-0'
      }`}>
        {/* Feedback Form */}
        {showFeedbackForm && (
          <FeedbackForm
            feedbackText={feedbackText}
            setFeedbackText={setFeedbackText}
            onSendFeedback={handleSendFeedback}
            onCancel={() => {
              setShowFeedbackForm(false);
              setFeedbackText('');
            }}
            isLoading={isLoading}
          />
        )}

        {/* Regular Input */}
        {!showApprovalButtons && !showFeedbackForm ? (
          <InputForm
            value={inputValue}
            onChange={setInputValue}
            onSend={handleSend}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            isLoading={isLoading}
            usePlanning={usePlanning}
            useExplainer={useExplainer}
            onPlanningToggle={handlePlanningToggle}
            onExplainerToggle={handleExplainerToggle}
            onFilesChange={handleFilesChange}
            attachedFiles={attachedFiles}
          />
        ) : null}
      </div>
    </div>
  );
};

export default ChatComponent;


