import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Send, ThumbsUp, ThumbsDown, RotateCcw } from 'lucide-react';
import { Message as MessageType, ChatComponentProps, HandlerResponse } from '../types/chat';
import { useUIState } from '../contexts/UIStateContext';
import Message from './Message';
import FeedbackForm from './FeedbackForm';
import LoadingIndicator from './LoadingIndicator';
import '../styles/scrollbar.css';

// Ephemeral tool indicator component - shows step history
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
    <div className="bg-blue-50 border-l-4 border-blue-200 p-3 mb-2 rounded-r-lg">
      <div className="space-y-2">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-center gap-2 text-sm">
            {step.status === 'completed' ? (
              <div className="w-3 h-3 bg-green-500 rounded-full flex-shrink-0 flex items-center justify-center">
                <span className="text-white text-xs">✓</span>
              </div>
            ) : (
              <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
            )}
            <span className={`font-medium ${step.status === 'completed' ? 'text-green-700' : 'text-blue-700'}`}>
              {step.status === 'completed' 
                ? `Step ${index + 1}: ${step.name || 'Unknown Tool'} (completed)` 
                : `Step ${index + 1}: ${step.name || 'Unknown Tool'}...`
              }
            </span>
            <span className={`text-xs ${step.status === 'completed' ? 'text-green-500' : 'text-blue-500'}`}>
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
  const inputRef = useRef<HTMLInputElement>(null);
  // Streaming UI state
  const [streamingActive, setStreamingActive] = useState<boolean>(false);
  
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
  const USE_STREAMING = state.useStreaming;
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

  // Observe execution status changes for debugging
  useEffect(() => {
    console.log('ChatComponent: executionStatus changed ->', state.executionStatus);
  }, [state.executionStatus]);


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
      id: Date.now() + 100, // Ensure unique ID
      role: 'assistant',
      content: response.message,
      timestamp: new Date(),
      messageType: 'explorer',
      checkpointId: response.explorerData.checkpoint_id, // ✅ FIXED: Use actual checkpoint_id
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

  // Helper function to handle response and create explorer message if needed
  const handleResponse = useCallback((response: HandlerResponse): string => {
    // If response has explorer data, create explorer message using separate method
    if (response.explorerData) {
      createExplorerMessage(response);
    }
    
    return response.message;
  }, [createExplorerMessage]);


const appendToMessageContent = useCallback(
  (messageId: number, appendContent: string): void => {
    let parsedContent: string | null = null;

    try {
      const parsed = JSON.parse(appendContent);
      if (parsed && typeof parsed === "object" && "content" in parsed) {
        parsedContent = parsed.content;
      }
    } catch {
    
    }

    const finalAppend = parsedContent ?? appendContent;
    setMessages(prev =>
      prev.map(m =>
        m.id === messageId
          ? { ...m, content: (m.content || "") + finalAppend }
          : m
      )
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
      threadId: contextThreadId || currentThreadId || undefined
    };

    setMessages(prev => [...prev, newUserMessage]);
  if (typeof onMessageCreated === 'function') {
    onMessageCreated(newUserMessage);
  }

    try {
      const response = await onSendMessage(userMessage, messages);
      if (response.isStreaming && response.streamingHandler) {
        // Prepare a streaming assistant message
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
          await response.streamingHandler(streamingMsgId, appendToMessageContent, (status, eventData) => {
            if (!status) return;
            console.log('ChatComponent: status via streamingHandler ->', status);            
            // Clear all tool indicators when streaming finishes
            if (status === 'finished' || status === 'user_feedback') {
              setToolStepHistory(null);
              
              setMessages(prev => prev.map(m => 
                m.id === streamingMsgId
                  ? { 
                      ...m, 
                      isStreaming: status !== 'finished', 
                      needsApproval: status === 'user_feedback' 
                    }
                  : m
              ));
              
              if (status === 'user_feedback') {
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
        } finally {
          setStreamingActive(false);
        }
      } else {
      const messageContent = handleResponse(response);
      console.log('ChatComponent: messageContent ->', messageContent);
      const assistantMessage: MessageType = {
        id: Date.now() + 1,
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
    setShowFeedbackForm(false);
    setFeedbackText('');
    setPendingApproval(null);
    setExecutionStatus('running');
    setLoading(true);
    
    

    try {
      // Call parent handler
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
              await (result as HandlerResponse).streamingHandler!(streamingMsgId, appendToMessageContent, (status, eventData) => {
                if (!status) return;
                
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
                
                // Clear all tool indicators when streaming finishes
                if (status === 'finished' || status === 'user_feedback') {
                  setToolStepHistory(null);
                  
                  setMessages(prev => prev.map(m => 
                    m.id === streamingMsgId
                      ? { 
                          ...m, 
                          isStreaming: status !== 'finished', 
                          needsApproval: status === 'user_feedback' 
                        }
                      : m
                  ));
                  
                  if (status === 'user_feedback') {
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
      const errorMsg = (error as Error).message || 'Something went wrong';
      const isTimeout = errorMsg.includes('timeout') || 
                       errorMsg.includes('30000ms exceeded') || 
                       errorMsg.includes('Request timed out') ||
                       errorMsg.includes('ECONNABORTED') ||
                       (error as any)?.code === 'ECONNABORTED';
      
      if (isTimeout) {
        // Mark the message as timed out and retryable
        setMessages(prev => prev.map(m => 
          m.id === messageId 
            ? { 
                ...m, 
                approved: false, 
                hasTimedOut: true, 
                canRetry: true, 
                retryAction: 'approve' as const,
                threadId: message.threadId
              }
            : m
        ));
      } else {
        const errorMessage: MessageType = {
          id: Date.now() + 1,
          role: 'assistant',
          content: `Error during approval: ${errorMsg}`,
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

    setShowFeedbackForm(false);
    setFeedbackText('');

    // Update message to show it's cancelled
    setMessages(prev => prev.map(m => 
      m.id === messageId 
        ? { ...m, disapproved: true, needsApproval: false }
        : m
    ));

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
              await (result as HandlerResponse).streamingHandler!(streamingMsgId, appendToMessageContent, (status, eventData) => {
                if (!status) return;
                
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
                
                // Clear all tool indicators when streaming finishes
                if (status === 'finished' || status === 'user_feedback') {
                  setToolStepHistory(null);
                  
                  setMessages(prev => prev.map(m => 
                    m.id === streamingMsgId
                      ? { 
                          ...m, 
                          isStreaming: status !== 'finished', 
                          needsApproval: status === 'user_feedback' 
                        }
                      : m
                  ));
                  
                  if (status === 'user_feedback') {
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
          const isNewPlan = messageContent.includes('This revised plan requires your approval');
          const resultMessage: MessageType = {
            id: Date.now() + 1,
            role: 'assistant',
            content: messageContent,
            timestamp: new Date(),
              needsApproval: isNewPlan
          };
          setMessages(prev => [...prev, resultMessage]);
          if (typeof onMessageCreated === 'function') {
            const finalMsg = messagesRef.current.find(m => m.id === Date.now() + 1);
            if (finalMsg) onMessageCreated(finalMsg);
          }
          if (isNewPlan) {
            setPendingApproval(resultMessage.id);
            }
          }
        }
      }
    } catch (error) {
      const errorMsg = (error as Error).message || 'Something went wrong';
      const isTimeout = errorMsg.includes('timeout') || 
                       errorMsg.includes('30000ms exceeded') || 
                       errorMsg.includes('Request timed out') ||
                       errorMsg.includes('ECONNABORTED') ||
                       (error as any)?.code === 'ECONNABORTED';
      
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
          content: `Error during feedback: ${errorMsg}`,
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

    // Update the original message to show it received feedback
    setMessages(prev => prev.map(m => 
      m.id === message.id 
        ? { ...m, needsApproval: false }
        : m
    ));

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
              await (result as HandlerResponse).streamingHandler!(streamingMsgId, appendToMessageContent, (status, eventData) => {
                if (!status) return;
                
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
                
                // Clear all tool indicators when streaming finishes
                if (status === 'finished' || status === 'user_feedback') {
                  setToolStepHistory(null);
                  
                  setMessages(prev => prev.map(m => 
                    m.id === streamingMsgId
                      ? { 
                          ...m, 
                          isStreaming: status !== 'finished', 
                          needsApproval: status === 'user_feedback' 
                        }
                      : m
                  ));
                  
                  if (status === 'user_feedback') {
                    setPendingApproval(streamingMsgId);
                  }
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
          const isNewPlan = messageContent.includes('This revised plan requires your approval');
          const resultMessage: MessageType = {
            id: Date.now() + 1,
            role: 'assistant',
            content: messageContent,
            timestamp: new Date(),
            needsApproval: isNewPlan
          };
          setMessages(prev => [...prev, resultMessage]);
          if (typeof onMessageCreated === 'function') {
            const finalMsg = messagesRef.current.find(m => m.id === Date.now() + 1);
            if (finalMsg) onMessageCreated(finalMsg);
          }
          if (isNewPlan) {
            setPendingApproval(resultMessage.id);
            }
          }
        }
      }
    } catch (error) {
      const errorMsg = (error as Error).message || 'Something went wrong';
      const isTimeout = errorMsg.includes('timeout') || 
                       errorMsg.includes('30000ms exceeded') || 
                       errorMsg.includes('Request timed out') ||
                       errorMsg.includes('ECONNABORTED') ||
                       (error as any)?.code === 'ECONNABORTED';
      
      if (isTimeout) {
        // Mark the message as timed out and retryable
        setMessages(prev => prev.map(m => 
          m.id === message.id 
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
          content: `Error during feedback: ${errorMsg}`,
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
    setShowFeedbackForm(false);
    setFeedbackText('');
    setPendingApproval(null);
    setExecutionStatus('running');
    setLoading(true);

    // Update message to show it's cancelled
    setMessages(prev => prev.map(m => 
      m.id === messageId 
        ? { ...m, disapproved: true, needsApproval: false }
        : m
    ));

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

  const clearChat = (): void => {
    setMessages([]);
    setShowFeedbackForm(false);
    setFeedbackText('');
    inputRef.current?.focus();
  };

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
      const errorMsg = (error as Error).message || 'Something went wrong';
      const isTimeout = errorMsg.includes('timeout') || 
                       errorMsg.includes('30000ms exceeded') || 
                       errorMsg.includes('Request timed out') ||
                       errorMsg.includes('ECONNABORTED') ||
                       (error as any)?.code === 'ECONNABORTED';
      
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
          content: `Retry failed: ${errorMsg}`,
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

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={`flex flex-col h-full min-h-0 overflow-hidden bg-white border border-gray-200 rounded-lg ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50 rounded-t-lg">
        <h3 className="font-semibold text-gray-900">Chat</h3>
        <div className="flex items-center gap-2">
          {streamingActive && (
            <div className="flex items-center text-blue-600 text-sm">
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse mr-2"></div>
              Streaming...
            </div>
          )}
          {USE_STREAMING && (
            <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
              Streaming Mode
            </span>
          )}
        <button
          onClick={clearChat}
          className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-lg transition-colors"
          title="Clear chat"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
        </div>
      </div>

      {/* Messages */}
      <div 
        className="flex-1 p-4 space-y-4 min-h-0 slim-scroll overflow-y-auto"
        style={{
          scrollbarWidth: 'thin',
          scrollbarColor: '#d1d5db transparent'
        }}
      >
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-8">
            <p>Start a conversation...</p>
          </div>
        ) : (
          messages.map((message) => (
            <React.Fragment key={message.id}>
              <Message
                message={message}
                onRetry={handleRetry}
              />
              
              {/* Show ephemeral tool indicators only for the streaming message */}
              {(() => {
                const shouldShow = message.isStreaming && 
                                 toolStepHistory?.messageId === message.id && 
                                 toolStepHistory.steps.length > 0;
                return shouldShow && (
                  <EphemeralToolIndicator steps={toolStepHistory.steps} />
                );
              })()}
            </React.Fragment>
          ))
        )}

    
        {/* Loading indicator */}
        {isLoading && (
          <LoadingIndicator 
            activeTools={toolStepHistory?.steps.filter(s => s.status === 'calling').map(s => s.name)} 
          />
        )}        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200">
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

        {/* Regular Input or Approval Buttons */}
        {pendingApproval && showApprovalButtons && !showFeedbackForm ? (
          // Show approval buttons when waiting for approval
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setShowFeedbackForm(true)}
              className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Send Feedback
            </button>
            <button
              onClick={() => pendingApproval && handleApprove(pendingApproval)}
              className="flex items-center gap-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              <ThumbsUp className="w-4 h-4" />
              Approve
            </button>
            <button
              onClick={() => pendingApproval && handleCancel(pendingApproval)}
              className="flex items-center gap-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              <ThumbsDown className="w-4 h-4" />
              Cancel
            </button>
          </div>
        ) : !showFeedbackForm ? (
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={placeholder}
              disabled={disabled || isLoading}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed text-gray-900 bg-white"
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || disabled || isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default ChatComponent;


