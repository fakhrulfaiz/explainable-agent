import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Message } from '../types/chat';
import { ExplorerRenderer } from './renderers/ExplorerRenderer';

interface MessageRendererProps {
  message: Message;
  onAction?: (action: string, data?: any) => void;
}

export const MessageRenderer: React.FC<MessageRendererProps> = ({ message, onAction }) => {
  const renderContent = () => {
    switch (message.messageType) {
      case 'explorer':
        return (
          <ExplorerRenderer 
            data={message.metadata?.explorerData}
            onOpenExplorer={() => onAction?.('openExplorer', message.metadata?.explorerData)}
            content={message.content}
          />
        );
      
      case 'message':
      default:
        return (
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
        );
    }
  };

  return (
    <div className="message-content">
      {renderContent()}
    </div>
  );
};
