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
          <div className="px-4 py-3 rounded-lg bg-primary text-primary-foreground">
            <div className="break-words prose max-w-none">
              <MessageRenderer message={message} onAction={handleAction} />
            </div>
          </div>
        ) : (
          <div className={`px-4 py-3 ${
            message.isError
              ? 'bg-destructive/15 text-destructive border border-destructive/30'
              : message.hasTimedOut
              ? 'bg-accent text-accent-foreground border border-border'
              : message.approved
              ? 'bg-accent text-accent-foreground border border-border'
              : message.disapproved
              ? 'bg-muted text-muted-foreground border border-border'
            : 'bg-background text-foreground'
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
        <div className={`text-xs text-muted-foreground mt-0.5 mb-2 ${
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
