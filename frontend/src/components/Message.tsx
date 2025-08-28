import React from 'react';
import { MessageComponentProps } from '../types/chat';
import ReactMarkdown from 'react-markdown';
import { RotateCcw } from 'lucide-react';

const Message: React.FC<MessageComponentProps> = ({ 
  message,
  onRetry
}) => {
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
              ? 'bg-gray-50 text-gray-700 border border-gray-200'
              : 'bg-gray-100 text-gray-900'
          }`}
        >
          <div className="break-words prose prose-sm max-w-none">
            <ReactMarkdown
              components={{
                p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
                ol: ({children}) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                ul: ({children}) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                li: ({children}) => <li className="text-inherit">{children}</li>,
                code: ({children}) => <code className="bg-gray-200 px-1 rounded text-sm font-mono">{children}</code>,
                strong: ({children}) => <strong className="font-semibold">{children}</strong>
              }}
            >
              {message.content}
            </ReactMarkdown>
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
            <span className="ml-2 text-gray-600 font-medium">Cancelled</span>
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
