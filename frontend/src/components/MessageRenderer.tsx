import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Message } from '../types/chat';
import { ExplorerRenderer } from './renderers/ExplorerRenderer';
import { markdownComponents } from '../utils/markdownComponents';

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
            components={markdownComponents}
            remarkPlugins={[remarkGfm]}
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
