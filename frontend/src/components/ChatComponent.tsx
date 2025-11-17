import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { ThumbsUp, ThumbsDown, ChevronDown } from 'lucide-react';
import { Message as MessageType, ChatComponentProps, HandlerResponse, ContentBlock, ToolCallsContent, createTextBlock, createToolCallsBlock, createExplorerBlock, createVisualizationsBlock } from '../types/chat';
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
  const [isAtBottom, setIsAtBottom] = useState<boolean>(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
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



  // Check if user is near the bottom of the messages container
  const checkIfNearBottom = (): boolean => {
    const container = messagesContainerRef.current;
    if (!container) return true;
    
    const threshold = 100; // pixels from bottom
    const scrollTop = container.scrollTop;
    const scrollHeight = container.scrollHeight;
    const clientHeight = container.clientHeight;
    
    return scrollHeight - scrollTop - clientHeight < threshold;
  };

  const scrollToBottom = (): void => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    // Update isAtBottom state after scrolling
    setTimeout(() => {
      setIsAtBottom(checkIfNearBottom());
    }, 100);
  };

  // Track scroll position to show/hide scroll-to-bottom button
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) {
      // If container doesn't exist yet, check again after a short delay
      const timeoutId = setTimeout(() => {
        const retryContainer = messagesContainerRef.current;
        if (retryContainer) {
          setIsAtBottom(checkIfNearBottom());
        }
      }, 100);
      return () => clearTimeout(timeoutId);
    }

    const handleScroll = () => {
      setIsAtBottom(checkIfNearBottom());
    };

    container.addEventListener('scroll', handleScroll);
    // Check initial position
    handleScroll();

    return () => {
      container.removeEventListener('scroll', handleScroll);
    };
  }, [messages]);

  // Also check scroll position when messages change
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (container && messages.length > 0) {
      // Small delay to ensure DOM is updated
      const timeoutId = setTimeout(() => {
        setIsAtBottom(checkIfNearBottom());
      }, 100);
      return () => clearTimeout(timeoutId);
    } else if (messages.length === 0) {
      setIsAtBottom(false);
    }
  }, [messages.length]);

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
    
    const explorerMessageId = Date.now() + Math.floor(Math.random() * 1000);
    const explorerMessage: MessageType = {
      id: explorerMessageId,
      role: 'assistant',
      content: response.message ? [createTextBlock(`text_${explorerMessageId}`, response.message, false)] : [],
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
      const vizMessageId = Date.now() + Math.floor(Math.random() * 1000) + 10000;
      const vizMessage: MessageType = {
        id: vizMessageId,
        role: 'assistant',
        content: response.message ? [createTextBlock(`text_${vizMessageId}`, response.message, false)] : [],
        timestamp: new Date(),
        messageType: 'visualization',
        checkpointId: response.checkpoint_id, // Add checkpoint ID for visualization messages
        metadata: { visualizations: response.visualizations },
        threadId: contextThreadId || currentThreadId || undefined
      };
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
      ? { ...m, content: [createTextBlock(`error_${streamingMsgId}`, `Error: ${streamErr.message || 'Streaming failed'}`, false)], messageStatus: 'error' as const, isStreaming: false }
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

// New callback for content blocks
const updateContentBlocksCallback = useCallback(
  (messageId: number, contentBlocks: ContentBlock[]): void => {
    setMessages(prev =>
      prev.map(m => {
        if (m.id === messageId) {
          return { ...m, content: contentBlocks };
        }
        return m;
      })
    );
  },
  []
);


  const handleSend = async (): Promise<void> => {
    if (!inputValue.trim() || isLoading || disabled || streamingActive) return;

    // Force scroll to bottom when user sends a message
    scrollToBottom();

    const userMessage = inputValue.trim();
    
    // If there's a pending approval, treat this as feedback
    if (pendingApproval) {
      const message = messages.find(m => m.id === pendingApproval);
      if (!message) return;

      // Add feedback as a user message
      const feedbackMessageId = Date.now();
      const feedbackMessage: MessageType = {
        id: feedbackMessageId,
        role: 'user',
        content: [createTextBlock(`text_${feedbackMessageId}`, userMessage, false)],
        timestamp: new Date()
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
              content: [], // Initialize with empty content blocks array
              timestamp: new Date(),
              isStreaming: true,
              needsApproval: false
            };
            setMessages(prev => [...prev, streamingMessage]);
            setStreamingActive(true);
            setPendingApproval(null);
            await (result as HandlerResponse).streamingHandler!(streamingMsgId, updateContentBlocksCallback, (status, eventData, responseType) => {
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
              content: (result as HandlerResponse).message ? [createTextBlock(`text_${finalId}`, (result as HandlerResponse).message || 'Response received', false)] : [],
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
      content: [createTextBlock(`text_${tempUserId}`, userMessage, false)],
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
          content: [], // Initialize with empty content blocks array
          timestamp: new Date(),
          threadId: contextThreadId || currentThreadId || undefined,
          isStreaming: true
        } as any;
        setMessages(prev => [...prev, streamingMessage]);
        setStreamingActive(true);

        try {
          // Track content blocks for the streaming message
          let currentContentBlocks: ContentBlock[] = [];
          
          await response.streamingHandler(streamingMsgId, updateContentBlocksCallback, (status, eventData, responseType) => {
            if (!status) return;
            
            // Handle content_block events
            if (status === 'content_block' && eventData) {
              try {
                const blockData = JSON.parse(eventData);
                const blockType = blockData.block_type;
                const blockId = blockData.block_id;
                const action = blockData.action;
                
                if (blockType === 'text') {
                  if (action === 'append_text') {
                    // Find existing text block or create new one
                    let textBlock = currentContentBlocks.find(b => b.id === blockId);
                    if (!textBlock) {
                      textBlock = createTextBlock(blockId, '', false);
                      currentContentBlocks = [...currentContentBlocks, textBlock];
                    }
                    // Append text content
                    (textBlock.data as any).text += blockData.content;
                    
        
                  } else if (action === 'finalize_text') {
                    // Update final text content
                    let textBlock = currentContentBlocks.find(b => b.id === blockId);
                    if (textBlock) {
                      (textBlock.data as any).text = blockData.content;
                    }
                  }
                } else if (blockType === 'tool_calls') {

                  const toolCallId = blockData.tool_call_id || `tool_calls_${streamingMsgId}`;
                  let consolidatedBlock = currentContentBlocks.find(b => b.id === toolCallId && b.type === 'tool_calls');
                  
                  if (action === 'stream_args') {
                    // Ensure consolidatedBlock exists
                    if (!consolidatedBlock) {
                      const toolCall = {
                        name: blockData.tool_name,
                        input: {},
                        status: 'pending' as const
                      };
                      consolidatedBlock = createToolCallsBlock(toolCallId, [toolCall], false);
                      currentContentBlocks = [...currentContentBlocks, consolidatedBlock];
                    }
                    
                    const toolCallsData = { ...consolidatedBlock.data } as ToolCallsContent;
                    let toolCallIndex = toolCallsData.toolCalls.findIndex(tc => tc.name === blockData.tool_name);
                    
                    // Create tool call if it doesn't exist
                    if (toolCallIndex < 0) {
                      toolCallsData.toolCalls.push({
                        name: blockData.tool_name,
                        input: {},
                        status: 'pending' as const
                      });
                      toolCallIndex = toolCallsData.toolCalls.length - 1;
                    }
                    
                    // Accumulate args_chunk and parse JSON when complete
                    const existingArgs = (toolCallsData.toolCalls[toolCallIndex] as any)._argsBuffer || '';
                    const accumulatedArgs = existingArgs + (blockData.args_chunk || '');
                    
                    // Store buffer for next chunk
                    (toolCallsData.toolCalls[toolCallIndex] as any)._argsBuffer = accumulatedArgs;
                    
                    // Try to parse the accumulated JSON - only update if valid JSON
                    try {
                      const parsedInput = JSON.parse(accumulatedArgs);
                      console.log('[stream_args] Updated input:', parsedInput);
                      
                      // Only update input when JSON is successfully parsed
                      // Create a new array with the updated tool call
                      const updatedToolCalls = [...toolCallsData.toolCalls];
                      const existingToolCall = updatedToolCalls[toolCallIndex];
                      
                      updatedToolCalls[toolCallIndex] = {
                        ...existingToolCall,
                        input: parsedInput,
                        // Preserve the buffer for potential future updates
                        _argsBuffer: accumulatedArgs
                      } as any;
                      
                      // Create new toolCallsData with updated tool calls
                      const updatedToolCallsData: ToolCallsContent = {
                        ...toolCallsData,
                        toolCalls: updatedToolCalls
                      };
                      
                      // Update the block in the array
                      currentContentBlocks = currentContentBlocks.map(block => 
                        block.id === toolCallId 
                          ? { ...block, data: updatedToolCallsData }
                          : block
                      );
                      
                      // Update UI immediately when JSON is valid
                      updateContentBlocksCallback(streamingMsgId, [...currentContentBlocks]);
                    } catch (e) {
                      // JSON is incomplete, don't update input yet - wait for more chunks
                      // Keep the existing input (or empty object) until JSON is complete
                    }
                    
                  } else if (action === 'update_tool_calls_explanation') {
                   
                    if (!consolidatedBlock) {
                      const newToolCallsBlock = createToolCallsBlock(toolCallId, [], false);
                      (newToolCallsBlock.data as ToolCallsContent).content = '';
                      consolidatedBlock = newToolCallsBlock;
                      currentContentBlocks = [...currentContentBlocks, consolidatedBlock];
                    }
              
                    const toolCallsData = { ...consolidatedBlock.data } as ToolCallsContent;
                    const existing = typeof toolCallsData.content === 'string' ? toolCallsData.content : '';
                    toolCallsData.content = existing + (blockData.content || '');
                    // Update the block in the array
                    currentContentBlocks = currentContentBlocks.map(block => 
                      block.id === toolCallId 
                        ? { ...block, data: toolCallsData }
                        : block
                    );
                  } else if (action === 'add_tool_call') {
                    const parsedArgs = blockData.args ? JSON.parse(blockData.args) : {};
                    
                    if (!consolidatedBlock) {
                      // Create new consolidated tool calls block
                      const toolCall = {
                        name: blockData.tool_name,
                        input: parsedArgs || {},  // Ensure input is always an object
                        status: 'pending' as const
                      };
                      consolidatedBlock = createToolCallsBlock(toolCallId, [toolCall], false);
                      currentContentBlocks = [...currentContentBlocks, consolidatedBlock];
                    
                    } else { 
                      // Add or update tool call in consolidated block
                      const toolCallsData = { ...consolidatedBlock.data } as ToolCallsContent;
                      const existingToolCallIndex = toolCallsData.toolCalls.findIndex(tc => tc.name === blockData.tool_name);
                      
                      if (existingToolCallIndex >= 0) {
                        // Update existing tool call with input, but preserve existing input if parsedArgs is empty
                        const existingInput = toolCallsData.toolCalls[existingToolCallIndex].input;
                        const newInput = (parsedArgs && Object.keys(parsedArgs).length > 0) ? parsedArgs : existingInput;
                        toolCallsData.toolCalls = [
                          ...toolCallsData.toolCalls.slice(0, existingToolCallIndex),
                          { ...toolCallsData.toolCalls[existingToolCallIndex], input: newInput },
                          ...toolCallsData.toolCalls.slice(existingToolCallIndex + 1)
                        ];
                      } else {
                        // Add new tool call
                        toolCallsData.toolCalls = [
                          ...toolCallsData.toolCalls,
                          {
                            name: blockData.tool_name,
                            input: parsedArgs || {},  // Ensure input is always an object
                            status: 'pending' as const
                          }
                        ];
                      }
                      
                      // Update the block in the array
                      currentContentBlocks = currentContentBlocks.map(block => 
                        block.id === toolCallId 
                          ? { ...block, data: toolCallsData }
                          : block
                      );
                    }
                    
                  } else if (action === 'update_tool_result') {
                    // Update tool result for specific tool call in consolidated block
                    if (consolidatedBlock) {
                      const toolCallsData = { ...consolidatedBlock.data } as ToolCallsContent;
                      const toolCallIndex = toolCallsData.toolCalls.findIndex(tc => tc.name === blockData.tool_name);
                      if (toolCallIndex >= 0) {
                        const existingToolCall = toolCallsData.toolCalls[toolCallIndex];
                        // Use input from blockData if provided and not empty, otherwise preserve existing input
                        const finalInput = (blockData.input && Object.keys(blockData.input).length > 0) 
                          ? blockData.input 
                          : (existingToolCall.input && Object.keys(existingToolCall.input).length > 0 
                              ? existingToolCall.input 
                              : {});
                        
                        // Update tool call with result and input
                        const updatedToolCall = {
                          ...existingToolCall,
                          input: finalInput,
                          output: blockData.output,
                          status: 'approved' as const
                        };
                        
                        toolCallsData.toolCalls = [
                          ...toolCallsData.toolCalls.slice(0, toolCallIndex),
                          updatedToolCall,
                          ...toolCallsData.toolCalls.slice(toolCallIndex + 1)
                        ];
                        
                        // Update the block in the array
                        currentContentBlocks = currentContentBlocks.map(block => 
                          block.id === toolCallId 
                            ? { ...block, data: toolCallsData }
                            : block
                        );
                        
                        // Update UI
                        updateContentBlocksCallback(streamingMsgId, [...currentContentBlocks]);
                      }
                    }
                    
                    // Also update ephemeral tool indicator when tool result arrives
                    handleToolEvents('tool_result', eventData, streamingMsgId);
                  }
                } else if (blockType === 'explorer' && action === 'add_explorer') {
                  // Add explorer content block with the actual explorer data
                  const explorerData = {
                    steps: blockData.steps || [],
                    final_result: blockData.final_result || {},
                    overall_confidence: blockData.overall_confidence || 0,
                    checkpoint_id: blockData.checkpoint_id,
                    query: blockData.query || '',
                    run_status: 'finished' // Default status for completed explorer blocks
                  };
                  const explorerBlock = createExplorerBlock(blockId, blockData.checkpoint_id, false, explorerData);
                  currentContentBlocks = [...currentContentBlocks, explorerBlock];
                } else if (blockType === 'visualizations' && action === 'add_visualizations') {
                  // Add visualizations content block with the actual visualization data
                  const visualizations = blockData.visualizations || [];
                  const vizBlock = createVisualizationsBlock(blockId, blockData.checkpoint_id, false, visualizations);
                  currentContentBlocks = [...currentContentBlocks, vizBlock];
                }
                
                // Update the message with current content blocks
                updateContentBlocksCallback(streamingMsgId, [...currentContentBlocks]);
                
                // Also update ephemeral tool indicator for tool events
                if (blockType === 'tool_calls') {
                  handleToolEvents('tool_call', eventData, streamingMsgId);
                }
              } catch (error) {
                console.error('Error handling content_block event:', error);
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
              
              // Add error as text content block
              const errorBlock = createTextBlock(`error_${Date.now()}`, errorText ? `Error: ${errorText}` : 'Unknown error', false);
              currentContentBlocks = [...currentContentBlocks, errorBlock];
              updateContentBlocksCallback(streamingMsgId, [...currentContentBlocks]);
              
              setMessages(prev => prev.map(m => 
                m.id === streamingMsgId
                  ? { 
                      ...m,
                      messageStatus: 'error' as const,
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
      const messageText = handleResponse(response);
      const backendId = response.backendMessageId;
      const tempId = Date.now() + 1;
      const finalId = backendId || tempId;
      const assistantMessage: MessageType = {
        id: finalId, // Use backend ID if available
        role: 'assistant',
        content: messageText ? [createTextBlock(`text_${finalId}`, messageText, false)] : [],
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
      const errorMessageId = Date.now() + 1;
      const errorMessage: MessageType = {
        id: errorMessageId,
        role: 'assistant',
        content: [createTextBlock(`error_${errorMessageId}`, `Error: ${(error as Error).message || 'Something went wrong'}`, false)],
        timestamp: new Date(),
        messageStatus: 'error' as const
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
        // Extract text content from content blocks for onApprove
        const textContent = Array.isArray(message.content) 
          ? message.content
              .filter(block => block.type === 'text')
              .map(block => (block.data as any).text)
              .join('\n')
          : message.content;
        const result = await onApprove(textContent, message);
        if (result) {
          if ((result as HandlerResponse).isStreaming && (result as HandlerResponse).streamingHandler) {
            const streamingMsgId = Date.now() + 1;
            const streamingMessage: MessageType = {
              id: streamingMsgId,
              role: 'assistant',
              content: [], // Initialize with empty content blocks array
              timestamp: new Date(),
              threadId: message.threadId || contextThreadId || currentThreadId || undefined,
              isStreaming: true
            } as any;
            setMessages(prev => [...prev, streamingMessage]);
            setStreamingActive(true);
            try {
              await (result as HandlerResponse).streamingHandler!(streamingMsgId, updateContentBlocksCallback, (status, eventData, responseType) => {
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
                  setMessages(prev => prev.map(m => {
                    if (m.id === streamingMsgId) {
                      const existingText = Array.isArray(m.content) 
                        ? m.content.filter(b => b.type === 'text').map(b => (b.data as any).text).join('\n')
                        : '';
                      const errorBlock = createTextBlock(`error_${streamingMsgId}`, errorText ? `Error: ${errorText}` : 'Error occurred', false);
                      return {
                        ...m,
                        content: existingText ? [createTextBlock(`text_${streamingMsgId}`, existingText, false), errorBlock] : [errorBlock],
                        messageStatus: 'error' as const,
                        isStreaming: false
                      };
                    }
                    return m;
                  }));
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
                  ? { ...m, content: [createTextBlock(`error_${streamingMsgId}`, `Error: ${(streamErr as Error).message || 'Streaming failed'}`, false)], messageStatus: 'error' as const, isStreaming: false }
                  : m
              ));

            } finally {
              setStreamingActive(false);
            }
          } else {
          const messageText = handleResponse(result as HandlerResponse);
          const backendId = (result as HandlerResponse).backendMessageId;
          const needsApproval = (result as HandlerResponse).needsApproval || false;
          const tempId = Date.now() + 1;
          const finalId = backendId || tempId;
            const resultMessage: MessageType = {
            id: finalId,
            role: 'assistant',
            content: messageText ? [createTextBlock(`text_${finalId}`, messageText, false)] : [],
            timestamp: new Date(),
            needsApproval: needsApproval,
            threadId: contextThreadId || currentThreadId || undefined
          };
          setMessages(prev => [...prev, resultMessage]);
          // Update blocks to approved status
          if (Array.isArray(message.content)) {
            const updatedContent = message.content.map(block => ({
              ...block,
              messageStatus: 'approved' as const,
              needsApproval: false
            }));
            await updateMessageFlags(messageId, { content: updatedContent });
          } else {
            // For legacy messages without content blocks, use messageStatus
            await updateMessageFlags(messageId, { messageStatus: 'approved' as const });
          }
          }
        }
      }
      
    } catch (error) {
      const isTimeout = isTimeoutError(error as Error);
      
      if (isTimeout) {
        // Update blocks to restore needsApproval
        if (Array.isArray(message.content)) {
          const updatedContent = message.content.map(block => ({
            ...block,
            approved: false,
            needsApproval: block.needsApproval !== false, // Restore if it was true
            disapproved: false
          }));
          await updateMessageFlags(messageId, { 
            content: updatedContent,
            messageStatus: 'timeout'
          });
        } else {
          // For legacy messages without content blocks, use messageStatus
          await updateMessageFlags(messageId, {
            messageStatus: 'timeout'
          });
        }
      } else {
        // Update blocks to restore needsApproval
        if (Array.isArray(message.content)) {
          const updatedContent = message.content.map(block => ({
            ...block,
            approved: false,
            needsApproval: block.needsApproval !== false, // Restore if it was true
            disapproved: false
          }));
          await updateMessageFlags(messageId, { content: updatedContent });
        } else {
          // For legacy messages without content blocks, use messageStatus
          await updateMessageFlags(messageId, { messageStatus: 'pending' });
        }
        
        const errorMessageId = Date.now() + 1;
        const errorMessage: MessageType = {
          id: errorMessageId,
          role: 'assistant',
          content: [createTextBlock(`error_${errorMessageId}`, `Error during approval: ${(error as Error).message || 'Something went wrong'}`, false)],
          timestamp: new Date(),
          messageStatus: 'error'
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

    // Update blocks to show they're cancelled
    if (Array.isArray(message.content)) {
      const updatedContent = message.content.map(block => ({
        ...block,
        messageStatus: 'rejected' as const,
        needsApproval: false
      }));
      await updateMessageFlags(message.id, { content: updatedContent });
    } else {
      // For legacy messages without content blocks, use messageStatus
      await updateMessageFlags(message.id, { messageStatus: 'rejected' as const });
    }

    try {
      // Call parent cancel handler
      if (onCancel) {
        // Extract text content from content blocks for onCancel
        const textContent = Array.isArray(message.content) 
          ? message.content
              .filter(block => block.type === 'text')
              .map(block => (block.data as any).text)
              .join('\n')
          : message.content;
        const result = await onCancel(textContent, message);
        
        // If the cancel handler returns a result, add it as a new message
        if (result) {
          const resultMessageId = Date.now() + 1;
          const resultText = typeof result === 'string' ? result : (result as HandlerResponse).message || '';
          const resultMessage: MessageType = {
            id: resultMessageId,
            role: 'assistant',
            content: resultText ? [createTextBlock(`text_${resultMessageId}`, resultText, false)] : [],
            timestamp: new Date(),
            needsApproval: false // Cancellation messages don't need approval
          };
          
          setMessages(prev => [...prev, resultMessage]);
        }
      }
    } catch (error) {
      // Add error message if cancellation fails
      const errorMessageId = Date.now() + 1;
      const errorMessage: MessageType = {
        id: errorMessageId,
        role: 'assistant',
        content: [createTextBlock(`error_${errorMessageId}`, `Error during cancellation: ${(error as Error).message || 'Something went wrong'}`, false)],
        timestamp: new Date(),
        messageStatus: 'error' as const
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
      }
  };

  const handleRetry = async (messageId: number): Promise<void> => {
    const message = messages.find(m => m.id === messageId);
    // Check if message has timeout status (can be retried)
    if (!message || message.messageStatus !== 'timeout') {
      return;
    }

    // Clear the timeout state and restore the message to pending status
    await updateMessageFlags(messageId, {
      messageStatus: 'pending' as const
    });

    try {
      // Call the parent's retry handler if available
      if (onRetry) {
        const result = await onRetry(message);
        
        // If the retry handler returns a result, add it as a new message
        if (result) {
          // Handle response (could be string or HandlerResponse)
          const messageText = handleResponse(result);
          const resultMessageId = Date.now() + 1;
          
          const resultMessage: MessageType = {
            id: resultMessageId,
            role: 'assistant',
            content: messageText ? [createTextBlock(`text_${resultMessageId}`, messageText, false)] : [],
            timestamp: new Date(),
            threadId: contextThreadId || currentThreadId || undefined
          };
          
          setMessages(prev => [...prev, resultMessage]);
        }
      } else {
        // Fallback to local retry logic if no parent handler
        // For timeout retries, we'll try to approve the message
        await handleApprove(messageId);
      }
    } catch (error) {
      const isTimeout = isTimeoutError(error as Error);
      
      // If retry fails, mark the message as having a timeout error again
      await updateMessageFlags(messageId, {
        messageStatus: 'timeout' as const
      });
      console.error('Retry failed:', error);
      
      // Also show the error message if it's not a timeout
      if (!isTimeout) {
        const errorMessageId = Date.now() + 1;
        const errorMessage: MessageType = {
          id: errorMessageId,
          role: 'assistant',
          content: [createTextBlock(`error_${errorMessageId}`, `Retry failed: ${(error as Error).message || 'Something went wrong'}`, false)],
          timestamp: new Date(),
          messageStatus: 'error' as const
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
        ref={messagesContainerRef}
        className={`relative flex-1 space-y-4 min-h-0 pb-40 overflow-y-auto slim-scroll ${threadTitle ? 'pt-38' : 'pt-8'}`}
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

      {/* Scroll to bottom button - fixed above input form, aligned with messages */}
      {!isAtBottom && messages.length > 0 && (
        <div className={`fixed ${sidebarExpanded ? 'md:left-82' : 'md:left-14'} right-0 bottom-42 md:bottom-42 z-30 pointer-events-none`}>
          <div className="max-w-3xl px-4 mx-auto">
            <div className="flex justify-end">
              <button
                onClick={() => scrollToBottom()}
                className="pointer-events-auto w-10 h-10 rounded-full bg-muted border-1 border-foreground/20 shadow-lg hover:bg-accent hover:border-foreground/30 hover:shadow-xl transition-all duration-200 flex items-center justify-center group"
                title="Scroll to bottom"
                aria-label="Scroll to bottom"
              >
                <ChevronDown className="w-5 h-5 text-foreground group-hover:text-foreground" />
              </button>
            </div>
          </div>
        </div>
      )}
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