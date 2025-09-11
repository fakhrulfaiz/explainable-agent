import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, ThumbsUp, ThumbsDown, RotateCcw } from 'lucide-react';
import { Message as MessageType, ChatComponentProps, HandlerResponse } from '../types/chat';
import Message from './Message';
import FeedbackForm from './FeedbackForm';
import LoadingIndicator from './LoadingIndicator';
import '../styles/scrollbar.css';

const ChatComponent: React.FC<ChatComponentProps> = ({ 
  onSendMessage, 
  onApprove, 
  onFeedback,
  onCancel,
  onRetry,
  onMessageCreated,
  currentThreadId,
  initialMessages = [],
  className = "",
  placeholder = "Type your message...",
  showApprovalButtons = true,
  disabled = false,
  renderBelowLastMessage
}) => {
  const [messages, setMessages] = useState<MessageType[]>(initialMessages);
  const [inputValue, setInputValue] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [pendingApproval, setPendingApproval] = useState<number | null>(null);
  const [showFeedbackForm, setShowFeedbackForm] = useState<boolean>(false);
  const [feedbackText, setFeedbackText] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = (): void => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (messages.length > 0) {
      scrollToBottom();
    }
  }, [messages]);


  // Update messages when initialMessages prop changes
  useEffect(() => {
    setMessages(initialMessages);
  }, [initialMessages]);

  // Helper function to handle response and create explorer message if needed
  const handleResponse = useCallback((response: string | HandlerResponse): string => {
    if (typeof response === 'string') {
      return response;
    }
    
    // If response has explorer data, create explorer message
    if (response.explorerData) {
      const explorerMessage: MessageType = {
        id: Date.now() + 100, // Ensure unique ID
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
        messageType: 'explorer',
        metadata: { explorerData: response.explorerData },
        threadId: currentThreadId || undefined
      };
      
      // Add explorer message after a short delay to ensure proper ordering
      setTimeout(() => {
        setMessages(prev => [...prev, explorerMessage]);
      }, 50);
    }
    
    return response.message;
  }, [currentThreadId]);

  const handleSend = async (): Promise<void> => {
    if (!inputValue.trim() || isLoading || disabled) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setIsLoading(true);
    setPendingApproval(null);

    // Add user message immediately
    const newUserMessage: MessageType = {
      id: Date.now(),
      role: 'user',
      content: userMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, newUserMessage]);

    try {
      // Call the parent's message handler
      const response = await onSendMessage(userMessage, messages);
      
      // Handle response (could be string or HandlerResponse)
      const messageContent = handleResponse(response);
      
      // Add assistant response
      const assistantMessage: MessageType = {
        id: Date.now() + 1,
        role: 'assistant',
        content: messageContent,
        timestamp: new Date(),
        needsApproval: showApprovalButtons,
        threadId: currentThreadId || undefined
      };

      setMessages(prev => [...prev, assistantMessage]);
      
      if (showApprovalButtons) {
        setPendingApproval(assistantMessage.id);
        setShowFeedbackForm(false);
        setFeedbackText('');
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
    } finally {
      setIsLoading(false);
    }
  };

  const handleApprove = async (messageId: number): Promise<void> => {
    const message = messages.find(m => m.id === messageId);
    if (!message) return;

    setPendingApproval(null);
    setShowFeedbackForm(false);
    setFeedbackText('');
    setIsLoading(true);
    
    // Update message to show it's approved
    setMessages(prev => prev.map(m => 
      m.id === messageId 
        ? { ...m, approved: true, needsApproval: false }
        : m
    ));

    try {
      // Call parent handler
      if (onApprove) {
        const result = await onApprove(message.content, message);
        
        if (result) {
          // Handle response (could be string or HandlerResponse)
          const messageContent = handleResponse(result);
          
          const resultMessage: MessageType = {
            id: Date.now() + 1,
            role: 'assistant',
            content: messageContent,
            timestamp: new Date()
          };
          
          setMessages(prev => [...prev, resultMessage]);
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
    } finally {
      setIsLoading(false);
    }
  };

  const handleFeedback = async (messageId: number): Promise<void> => {
    const message = messages.find(m => m.id === messageId);
    if (!message) return;

    setPendingApproval(null);
    setShowFeedbackForm(false);
    setFeedbackText('');
    setIsLoading(true);

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
        
        // If the feedback handler returns a result, add it as a new message
        if (result) {
          // Handle response (could be string or HandlerResponse)
          const messageContent = handleResponse(result);
          
          // Check if this is a cancellation message or a new plan
          const isNewPlan = messageContent.includes('This revised plan requires your approval');
          
          const resultMessage: MessageType = {
            id: Date.now() + 1,
            role: 'assistant',
            content: messageContent,
            timestamp: new Date(),
            needsApproval: isNewPlan // Only new plans need approval, not cancellations
          };
          
          setMessages(prev => [...prev, resultMessage]);
          
          if (isNewPlan) {
            setPendingApproval(resultMessage.id);
            
            // Notify parent that a new message was created that needs approval
            if (onMessageCreated) {
              onMessageCreated(resultMessage.id);
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
      setIsLoading(false);
    }
  };

  const handleSendFeedback = async (): Promise<void> => {
    if (!feedbackText.trim() || !pendingApproval) return;

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
    setFeedbackText('');
    setShowFeedbackForm(false);
    setPendingApproval(null);
    setIsLoading(true);

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
        
        // If the feedback handler returns a result, add it as a new message
        if (result) {
          // Handle response (could be string or HandlerResponse)
          const messageContent = handleResponse(result);
          
          const isNewPlan = messageContent.includes('This revised plan requires your approval');
          
          const resultMessage: MessageType = {
            id: Date.now() + 1,
            role: 'assistant',
            content: messageContent,
            timestamp: new Date(),
            needsApproval: isNewPlan
          };
          
          setMessages(prev => [...prev, resultMessage]);
          
          if (isNewPlan) {
            setPendingApproval(resultMessage.id);
            
            // Notify parent that a new message was created that needs approval
            if (onMessageCreated) {
              onMessageCreated(resultMessage.id);
            }
          }
        }
      }

    } catch (error) {
      const errorMessage: MessageType = {
        id: Date.now() + 1,
        role: 'assistant',
        content: `Error: ${(error as Error).message || 'Something went wrong'}`,
        timestamp: new Date(),
        isError: true
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async (messageId: number): Promise<void> => {
    const message = messages.find(m => m.id === messageId);
    if (!message) return;

    setPendingApproval(null);
    setShowFeedbackForm(false);
    setFeedbackText('');
    setIsLoading(true);

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
          // Handle response (could be string or HandlerResponse)
          const messageContent = handleResponse(result);
          
          const resultMessage: MessageType = {
            id: Date.now() + 1,
            role: 'assistant',
            content: messageContent,
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
      setIsLoading(false);
    }
  };

  const clearChat = (): void => {
    setMessages([]);
    setPendingApproval(null);
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
    setIsLoading(true);

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
            threadId: currentThreadId || undefined
          };
          
          setMessages(prev => [...prev, resultMessage]);
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
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={`flex flex-col h-full bg-white border border-gray-200 rounded-lg ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50 rounded-t-lg">
        <h3 className="font-semibold text-gray-900">Chat</h3>
        <button
          onClick={clearChat}
          className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-lg transition-colors"
          title="Clear chat"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div 
        className="flex-1 p-4 space-y-4 min-h-0 slim-scroll"
        style={{
          overflowY: 'overlay' as any,
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
            <Message
              key={message.id}
              message={message}
              onRetry={handleRetry}
            />
          ))
        )}

        {/* Below-last-message slot */}
        {messages.length > 0 && renderBelowLastMessage}

        {/* Loading indicator */}
        {isLoading && <LoadingIndicator />}

        <div ref={messagesEndRef} />
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
            </button>
            <button
              onClick={() => handleApprove(pendingApproval)}
              className="flex items-center gap-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              <ThumbsUp className="w-4 h-4" />
              Approve
            </button>
            <button
              onClick={() => handleCancel(pendingApproval)}
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
