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
        // This would need to be passed down from parent component
        // For now, we'll use a custom event or callback
        if ((window as any).openExplorer) {
          (window as any).openExplorer(data);
        }
        break;
    }
  };
 
  if (message.messageType === 'explorer') {
    return (
      <div className="w-full mb-4">
        <MessageRenderer message={message} onAction={handleAction} />
      </div>
    );
  }

  // Regular message bubble layout
  return (
    <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
        {/* Message bubble */}
        <div
          className={`px-4 py-3 rounded-lg ${
            message.role === 'user'
              ? 'bg-blue-600 text-white'
              : message.isError
              ? 'bg-red-50 text-red-700 border border-red-200'
              : message.hasTimedOut
              ? 'bg-orange-50 text-orange-700 border border-orange-200'
              : message.approved
              ? 'bg-green-50 text-green-700 border border-green-200'
              : message.disapproved
              ? 'bg-red-50 text-gray-700 border border-red-200'
              : 'bg-gray-100 text-gray-900'
          }`}
        >
          <div className="break-words prose prose-sm max-w-none">
            <MessageRenderer message={message} onAction={handleAction} />
          </div>
        </div>

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
        <div className={`text-xs text-gray-500 mt-1 ${
          message.role === 'user' ? 'text-right' : 'text-left'
        }`}>
          {message.timestamp.toLocaleTimeString()}
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
