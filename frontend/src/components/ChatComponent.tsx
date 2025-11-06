import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { Message as MessageType, ChatComponentProps, HandlerResponse } from '../types/chat';
import { useUIState } from '../contexts/UIStateContext';
import Message from './Message';
import GeneratingIndicator from './GeneratingIndicator';
import InputForm from './InputForm';
import ThreadTitle from './ThreadTitle';
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
    <div className="bg-muted border-l-4 border-border p-3 mb-2 rounded-r-lg">
      <div className="space-y-2">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-center gap-2 text-sm">
            {step.status === 'completed' ? (
              <div className="w-3 h-3 bg-foreground rounded-full flex-shrink-0 flex items-center justify-center">
                <span className="text-background text-xs">✓</span>
              </div>
            ) : (
              <div className="w-3 h-3 border-2 border-foreground border-t-transparent rounded-full animate-spin flex-shrink-0" />
            )}
            <span className={`font-medium ${step.status === 'completed' ? 'text-foreground' : 'text-muted-foreground'}`}>
              {step.status === 'completed' 
                ? `Step ${index + 1}: ${step.name || 'Unknown Tool'} (completed)` 
                : `Step ${index + 1}: ${step.name || 'Unknown Tool'}...`
              }
            </span>
            <span className={`text-xs ${step.status === 'completed' ? 'text-muted-foreground' : 'text-muted-foreground'}`}>
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
  onMessageUpdated,
  threadTitle,
  onTitleChange,
  sidebarExpanded = true
}) => {
 
  // Use UI state context for loading and execution state
  const { state, setExecutionStatus, setLoading } = useUIState();
  
  const [messages, setMessages] = useState<MessageType[]>(initialMessages);
  const [inputValue, setInputValue] = useState<string>('');
  const [pendingApproval, setPendingApproval] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // Streaming UI state
  const [streamingActive, setStreamingActive] = useState<boolean>(false);
  const useStreaming = state.useStreaming;
  
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
    }, 50);
  }, [contextThreadId, currentThreadId]);

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
      }, 50);
    }
    return response.message;
  }, [createExplorerMessage, contextThreadId, currentThreadId]);


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

// Helper function to update message flags and trigger callback
const updateMessageFlags = useCallback(async (
  messageId: number,
  updates: Partial<MessageType>
) => {
  // Get the current message before updating
  const currentMessage = messages.find(m => m.id === messageId);
  if (!currentMessage) {
    console.warn('Message not found for update:', messageId);
    return;
  }

  // Update the local state
  updateMessage(messageId, updates);

  // Trigger the callback if provided - parent will handle persistence
  if (onMessageUpdated) {
    const updatedMessage = { ...currentMessage, ...updates };
    onMessageUpdated(updatedMessage);
  }
}, [updateMessage, onMessageUpdated, messages]);

// Helper function to handle tool events
const handleToolEvents = useCallback((
  status: string,
  eventData: string | undefined,
  streamingMsgId: number
) => {
  // Handle tool call start - show temporary indicator
  if (status === 'tool_call' && eventData) {
    try {
      const toolData = JSON.parse(eventData);
      const toolId = toolData.tool_id;
      const toolName = toolData.tool_name || 'Unknown Tool';
      
      // Only add to indicator if we have a real tool_id (not temp key)
      if (toolId && !toolId.toString().startsWith('temp_')) {
        setToolStepHistory(prev => {
          if (!prev || prev.messageId !== streamingMsgId) {
            // Create new history
            return {
              messageId: streamingMsgId,
              steps: [{
                name: toolName,
                id: toolId,
                startTime: Date.now(),
                status: 'calling' as const
              }]
            };
          }
          
          // Check if step already exists
          const existingStep = prev.steps.find(s => s.id === toolId);
          
          if (existingStep) {
            // Update existing step (for incremental updates)
            const updatedSteps = prev.steps.map(step =>
              step.id === toolId ? { ...step, name: toolName } : step
            );
            return { ...prev, steps: updatedSteps };
          } else {
            // Add new step
            return {
              ...prev,
              steps: [...prev.steps, {
                name: toolName,
                id: toolId,
                startTime: Date.now(),
                status: 'calling' as const
              }]
            };
          }
        });
      }
    } catch (error) {
      console.error('Error handling tool_call for indicator:', error);
    }
  }
  
  // Handle tool result - update the indicator
  if (status === 'tool_result' && eventData) {
    try {
      const resultData = JSON.parse(eventData);
      const toolCallId = resultData.tool_call_id;
      
      setToolStepHistory(prev => {
        if (!prev || prev.messageId !== streamingMsgId) return prev;
        
        const updatedSteps = prev.steps.map(step => 
          step.id === toolCallId 
            ? { ...step, status: 'completed' as const, endTime: Date.now() }
            : step
        );
        return { ...prev, steps: updatedSteps };
      });
    } catch (error) {
      console.error('Error handling tool_result for indicator:', error);
    }
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
    
    // If there's a pending approval, treat this as feedback
    if (pendingApproval) {
      const message = messages.find(m => m.id === pendingApproval);
      if (!message) return;

      // Add feedback as a user message
      const feedbackMessage: MessageType = {
        id: Date.now(),
        role: 'user',
        content: userMessage,
        timestamp: new Date(),
        isFeedback: true
      };

      setMessages(prev => [...prev, feedbackMessage]);
      setInputValue('');
      
      // Call the feedback handler
      if (onFeedback) {
        console.log('onFeedback was called');
        const result = await onFeedback(userMessage, message);
        console.log('result', result);
        // Handle the result similar to handleSendFeedback
        if (result) {
          if ((result as HandlerResponse).isStreaming && (result as HandlerResponse).streamingHandler) {
            const streamingMsgId = Date.now() + 1;
            const streamingMessage: MessageType = {
              id: streamingMsgId,
              role: 'assistant',
              content: '',
              timestamp: new Date(),
              isStreaming: true,
              needsApproval: false
            };
            setMessages(prev => [...prev, streamingMessage]);
            setStreamingActive(true);
            setPendingApproval(null);
            await (result as HandlerResponse).streamingHandler!(streamingMsgId, updateMessageCallback, (status, eventData, responseType) => {
              if (!status) return;
              
              // Handle tool events
              handleToolEvents(status, eventData, streamingMsgId);

              // Handle streaming status updates
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
            setStreamingActive(false);
          } else {
            // Use backend message ID if available, otherwise generate one
            const backendId = (result as HandlerResponse).backendMessageId;
            const tempId = Date.now();
            const finalId = backendId !== undefined && backendId !== null ? backendId : tempId;
            
            const assistantMessage: MessageType = {
              id: finalId,
              role: 'assistant',
              content: (result as HandlerResponse).message || 'Response received',
              timestamp: new Date(),
              needsApproval: (result as HandlerResponse).needsApproval || false
            };
            setMessages(prev => [...prev, assistantMessage]);
            if (assistantMessage.needsApproval) {
              setPendingApproval(assistantMessage.id);
            } else {
              setPendingApproval(null);
            }
          }
        }
      }
      return;
    }

    // Regular message handling
    setInputValue('');
    setPendingApproval(null);

    const tempUserId = Date.now();
    const newUserMessage: MessageType = {
      id: tempUserId,
      role: 'user',
      content: userMessage,
      timestamp: new Date(),
      threadId: contextThreadId || currentThreadId || undefined,
      metadata: {
        attachedFiles: attachedFiles
      }
    };

    setMessages(prev => [...prev, newUserMessage]);
  

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
            
            // Handle tool_call event - parse complete args and update message
            if (status === 'tool_call' && eventData) {
              try {
                const toolData = JSON.parse(eventData);
                const toolId = toolData.tool_id || toolData.tool_call_id || `tool_${Date.now()}`;
                const toolName = toolData.tool_name || 'Unknown Tool';
                const argsString = toolData.args || '';
                
                // Parse complete args directly
                let parsedArgs: any = {};
                if (argsString) {
                  try {
                    parsedArgs = JSON.parse(argsString);
                  } catch (error) {
                    // If parsing fails, keep empty object
                    console.warn('Failed to parse tool args:', error);
                  }
                }
                
                // Update existing message or create new one
                setMessages(prev => {
                  const existingMessage = prev.find(m => 
                    m.messageType === 'tool_call' && 
                    m.metadata?.toolCalls?.some((tc: any) => tc.id === toolId)
                  );
                  
                  if (existingMessage) {
                    // Update existing
                    return prev.map(m => {
                      if (m.id === existingMessage.id && m.metadata?.toolCalls) {
                        return {
                          ...m,
                          metadata: {
                            ...m.metadata,
                            toolCalls: m.metadata.toolCalls.map((tc: any) =>
                              tc.id === toolId ? { ...tc, input: parsedArgs } : tc
                            )
                          }
                        };
                      }
                      return m;
                    });
                  } else {
                    // Create new
                    const toolCallMessageId = Date.now() + Math.random();
                    const toolCallMessage: MessageType = {
                      id: toolCallMessageId,
                      role: 'assistant',
                      content: '',
                      timestamp: new Date(),
                      messageType: 'tool_call',
                      threadId: contextThreadId || currentThreadId || undefined,
                      metadata: {
                        toolCalls: [{
                          id: toolId,
                          name: toolName,
                          input: parsedArgs,
                          status: 'pending' as const
                        }]
                      }
                    };
                    return [...prev, toolCallMessage];
                  }
                });
                
                // Also update ephemeral tool indicator
                handleToolEvents(status, eventData, streamingMsgId);
              } catch (error) {
                console.error('Error handling tool_call event:', error);
              }
              return;
            }
            
            // Handle tool_result event - update with output and full input from backend
            if (status === 'tool_result' && eventData) {
              try {
                const resultData = JSON.parse(eventData);
                const toolCallId = resultData.tool_call_id;
                let toolOutput = resultData.output || resultData.content || '';
                const toolInput = resultData.input || {}; // Full input from backend
                
                // Try to parse output as JSON, if it fails use original
                if (typeof toolOutput === 'string' && toolOutput.trim()) {
                  try {
                    const parsedOutput = JSON.parse(toolOutput);
                    toolOutput = parsedOutput;
                  } catch (error) {
                    // Not valid JSON, use original string output
                  }
                }
                
                // Update message with output and full input
                setMessages(prev => prev.map(m => {
                  if (m.messageType === 'tool_call' && m.metadata?.toolCalls) {
                    const updatedToolCalls = m.metadata.toolCalls.map((tc: any) => 
                      tc.id === toolCallId
                        ? { ...tc, input: toolInput, output: toolOutput, status: 'approved' as const }
                        : tc
                    );
                    if (updatedToolCalls.some((tc: any) => tc.id === toolCallId)) {
                      return {
                        ...m,
                        metadata: { ...m.metadata, toolCalls: updatedToolCalls }
                      };
                    }
                  }
                  return m;
                }));
                
                handleToolEvents(status, eventData, streamingMsgId);
              } catch (error) {
                console.error('Error handling tool_result event:', error);
              }
              return;
            }
            
            // Handle tool events for ephemeral indicators
            handleToolEvents(status, eventData, streamingMsgId);
            
            // Handle error status from agent and append error message
            if (status === 'error') {
              let errorText = '';
              try {
                if (eventData) {
                  const parsed = JSON.parse(eventData);
                  errorText = parsed?.error || parsed?.message || String(eventData);
                }
              } catch {
                errorText = eventData || 'Unknown error';
              }
              setMessages(prev => prev.map(m => 
                m.id === streamingMsgId
                  ? { 
                      ...m,
                      content: (m.content || '') + (errorText ? `\nError: ${errorText}` : ''),
                      isError: true,
                      isStreaming: false
                    }
                  : m
              ));
              return;
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

            if (status === 'completed_payload') {
            }
            else if (status === 'visualizations_ready') {
            }
            
            
          });               
        } catch (streamErr) {
          handleStreamingError(streamErr as Error, streamingMsgId);
        } finally {
          setStreamingActive(false);
        }
      } else {
      const messageContent = handleResponse(response);
      const backendId = response.backendMessageId;
      const tempId = Date.now() + 1;
      const finalId = backendId || tempId;
      const assistantMessage: MessageType = {
        id: finalId, // Use backend ID if available
        role: 'assistant',
        content: messageContent,
        timestamp: new Date(),
        needsApproval: response.needsApproval,
        threadId: contextThreadId || currentThreadId || undefined
      };
        setMessages(prev => [...prev, assistantMessage]);
        
      if (response.needsApproval) {
        setPendingApproval(assistantMessage.id);
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
    
    setPendingApproval(null);
    setExecutionStatus('running');
    setLoading(true);

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
                
                // Handle error status from agent and append error message
                if (status === 'error') {
                  let errorText = '';
                  try {
                    if (eventData) {
                      const parsed = JSON.parse(eventData);
                      errorText = parsed?.error || parsed?.message || String(eventData);
                    }
                  } catch {
                    errorText = eventData || 'Unknown error';
                  }
                  setMessages(prev => prev.map(m => 
                    m.id === streamingMsgId
                      ? { 
                          ...m,
                          content: (m.content || '') + (errorText ? `\nError: ${errorText}` : ''),
                          isError: true,
                          isStreaming: false
                        }
                      : m
                  ));
                  return;
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

            } finally {
              setStreamingActive(false);
            }
          } else {
          const messageContent = handleResponse(result as HandlerResponse);
          const backendId = (result as HandlerResponse).backendMessageId;
          const needsApproval = (result as HandlerResponse).needsApproval || false;
          const tempId = Date.now() + 1;
          const finalId = backendId || tempId;
            const resultMessage: MessageType = {
            id: finalId,
            role: 'assistant',
            content: messageContent,
            timestamp: new Date(),
            needsApproval: needsApproval,
            threadId: contextThreadId || currentThreadId || undefined
          };
          setMessages(prev => [...prev, resultMessage]);
          await updateMessageFlags(messageId, { approved: true, needsApproval: false });
          }
        }
      }
      
    } catch (error) {
      const isTimeout = isTimeoutError(error as Error);
      
      if (isTimeout) {
        
        await updateMessageFlags(messageId, {
          approved: false,
          needsApproval: true, // Restore needsApproval since it failed
          hasTimedOut: true, 
          canRetry: true, 
          retryAction: 'approve'
        });
      } else {
        
        await updateMessageFlags(messageId, { approved: false, needsApproval: true });
        
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
    
    setPendingApproval(null);
    setExecutionStatus('running');
    setLoading(true);

    // Update message to show it's cancelled
    await updateMessageFlags(message.id, { disapproved: true, needsApproval: false });

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
    } finally {
      setLoading(false);
      }
  };

  const handleRetry = async (messageId: number): Promise<void> => {
    const message = messages.find(m => m.id === messageId);
    if (!message || !message.canRetry || !message.retryAction) {
      return;
    }


    // Clear the timeout state and restore the message to its pre-timeout state
    await updateMessageFlags(messageId, {
      hasTimedOut: false, 
      canRetry: false, 
      retryAction: undefined 
    });

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
        }
      } else {
        // Fallback to local retry logic if no parent handler
        if (message.retryAction === 'approve') {
          await handleApprove(messageId);
        } else if (message.retryAction === 'feedback') {
          // For feedback retry, we need to provide feedback content
          // Since we don't have the original feedback content, we'll use a generic message
          if (onFeedback) {
            const result = await onFeedback('Retrying previous action', message);
            if (result) {
              const messageContent = handleResponse(result as HandlerResponse);
              const needsApproval = (result as HandlerResponse).needsApproval || false;
              const backendId = (result as HandlerResponse).backendMessageId;
              const tempId = Date.now() + 1;
              const finalId = backendId !== undefined && backendId !== null ? backendId : tempId;
              
              const resultMessage: MessageType = {
                id: finalId,
                role: 'assistant',
                content: messageContent,
                timestamp: new Date(),
                needsApproval: needsApproval,
                threadId: contextThreadId || currentThreadId || undefined
              };
              
              setMessages(prev => [...prev, resultMessage]);
              if (needsApproval) {
                setPendingApproval(resultMessage.id);
              }
            }
          }
        }
      }
    } catch (error) {
      const isTimeout = isTimeoutError(error as Error);
      
      // If retry fails, mark the message as having a timeout error again
      await updateMessageFlags(messageId, {
        hasTimedOut: true, 
        canRetry: true,
        retryAction: message.retryAction // Preserve the original retry action
      });
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
      {/* Thread Title - responsive background */}
      {threadTitle && (
        <>
           {/* Mobile: Full-width background with gradient bottom */}
           <div className={`md:hidden fixed top-0 left-0 right-0 z-30 transition-[left] duration-300 ease-in-out`}>
             {/* Main background */}
             <div className="bg-background py-3 pr-4 pl-14">
               <ThreadTitle 
                 title={threadTitle}
                 threadId={currentThreadId || undefined}
                 onTitleChange={onTitleChange}
               />
             </div>
             {/* Very sharp gradient fade at bottom */}
             <div className="h-3 bg-gradient-to-b from-background via-background/20 to-transparent"></div>
           </div>

          {/* Desktop: Background with gradient bottom */}
         <div className={`hidden md:block fixed top-0 left-0 right-0 z-30 transition-[left] duration-300 ease-in-out`}>
            {/* Main background */}
            <div className={`bg-background py-3 pr-4 ${sidebarExpanded ? 'pl-84' : 'pl-16'} transition-[padding-left] duration-300 ease-in-out`}>
              <ThreadTitle 
                title={threadTitle}
                threadId={currentThreadId || undefined}
                onTitleChange={onTitleChange}
              />
            </div>
            {/* Very sharp gradient fade at bottom */}
            <div className="h-3 bg-gradient-to-b from-background via-background/20 to-transparent"></div>
          </div>
        </>
      )}
      
      {/* Messages - scrollable area with padding for fixed input and header */}
      <div 
        className={`flex-1 space-y-4 min-h-0 pb-40 overflow-y-auto slim-scroll ${threadTitle ? 'pt-38' : 'pt-8'}`}
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
        {!useStreaming && isLoading && (
          <GeneratingIndicator 
            activeTools={toolStepHistory?.steps.filter(s => s.status === 'calling').map(s => s.name)} 
          />
        )}
        <div ref={messagesEndRef} />
        </div>
      </div>

     
      <div className={`fixed left-0 ${sidebarExpanded ? 'md:left-82' : 'md:left-14'} right-0 z-10 transition-all duration-300 ease-in-out ${
        messages.length === 0 
          ? 'bottom-0 pb-3 md:top-1/2 md:transform md:-translate-y-1/2 md:flex md:items-center md:justify-center' 
          : 'bottom-0 pb-3 md:flex md:items-center'
      }`}>
       
        <div className={`${messages.length === 0 ? 'max-w-4xl px-6' : 'max-w-3xl px-4'} min-w-[320px] w-full mx-auto`}>
          {messages.length === 0 && (
            <div className="hidden md:block mb-5 text-center text-muted-foreground">
              <span className="text-3xl">Hi User! Start a conversation</span>
            </div>
          )}
          <InputForm
            value={inputValue}
            onChange={setInputValue}
            onSend={handleSend}
            onKeyDown={handleKeyDown}
            placeholder={pendingApproval ? "Your feedback..." : placeholder}
            disabled={disabled}
            isLoading={isLoading}
            usePlanning={usePlanning}
            useExplainer={useExplainer}
            onPlanningToggle={handlePlanningToggle}
            onExplainerToggle={handleExplainerToggle}
            onFilesChange={handleFilesChange}
            attachedFiles={attachedFiles}
          />
        </div>
      </div>
    </div>
  );
};

export default ChatComponent;