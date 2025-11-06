import React from 'react';
import { MessageComponentProps } from '../types/chat';
import { MessageRenderer } from './MessageRenderer';
import { RotateCcw } from 'lucide-react';

const Message: React.FC<MessageComponentProps> = ({ 
  message,
  onRetry
}) => {
  const handleAction = (action: string, data?: any) => {
    switch (action) {
      case 'openExplorer':
        if ((window as any).openExplorer) {
          (window as any).openExplorer(data);
        }
        break;
      case 'openVisualization':
        if ((window as any).openVisualization) {
          (window as any).openVisualization(data);
        }
        break;
    }
  };
 
  if (message.messageType === 'explorer' || message.messageType === 'visualization' || message.messageType === 'tool_call') {
    return (
      <div className="w-full mb-4">
        <MessageRenderer message={message} onAction={handleAction} />
      </div>
    );
  }

  if (!message.content || message.content.trim().length === 0) {
    return null;
  }
  // Regular message layout
  return (
    <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`${message.role === 'user' ? 'max-w-[80%] order-2' : 'w-full order-1'}`}>
        {/* Message content */}
        {message.role === 'user' ? (
          <div className="px-4 py-3 rounded-lg bg-gray-800 dark:bg-neutral-700 text-white dark:text-neutral-100">
            <div className="break-words prose max-w-none">
              <MessageRenderer message={message} onAction={handleAction} />
            </div>
          </div>
        ) : (
          <div className={`px-4 py-3 ${
            message.isError
              ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
              : message.hasTimedOut
              ? 'bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400 border border-orange-200 dark:border-orange-800'
              : message.approved
              ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
              : message.disapproved
              ? 'bg-red-50 dark:bg-red-900/20 text-gray-700 dark:text-gray-300 border border-red-200 dark:border-red-800'
            : 'bg-white dark:bg-neutral-800 text-gray-800 dark:text-neutral-200'
          }`}>
            <div className="break-words prose max-w-none">
              <MessageRenderer message={message} onAction={handleAction} />
            </div>
          </div>
        )}

        {/* Retry button for timed-out messages */}
        {message.hasTimedOut && message.canRetry && onRetry && (
          <div className="mt-2">
            <button
              onClick={() => onRetry(message.id)}
              className="flex items-center gap-1 px-3 py-1 bg-orange-600 text-white text-sm rounded hover:bg-orange-700 transition-colors"
            >
              <RotateCcw className="w-3 h-3" />
              Retry {message.retryAction}
            </button>
          </div>
        )}

        {/* Timestamp and status */}
        <div className={`text-xs text-gray-500 dark:text-neutral-400 mt-0.5 mb-2 ${
          message.role === 'user' ? 'text-right' : 'text-left'
        }`}>
          {message.isFeedback && (
            <span className="ml-2 text-blue-600 font-medium">Feedback</span>
          )}
          {message.approved && (
            <span className="ml-2 text-green-600 font-medium">✓ Approved</span>
          )}
          {message.disapproved && (
            <span className="ml-2 text-red-600 font-medium">Cancelled</span>
          )}
          {message.hasTimedOut && (
            <span className="ml-2 text-orange-600 font-medium">Timed out</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default Message;
