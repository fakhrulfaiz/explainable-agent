import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Message } from '../types/chat';
import { ExplorerMessage } from './messages/ExplorerMessage';
import { markdownComponents } from '../utils/markdownComponents';
import VisualizationMessage from './messages/VisualizationMessage';
import { ToolCallMessage } from './messages/ToolCallMessage';

interface MessageRendererProps {
  message: Message;
  onAction?: (action: string, data?: any) => void;
}

export const MessageRenderer: React.FC<MessageRendererProps> = ({ message, onAction }) => {
  const renderContent = () => {
    switch (message.messageType) {
      case 'explorer':
        return (
          <ExplorerMessage 
            data={message.metadata?.explorerData}
            onOpenExplorer={() => onAction?.('openExplorer', message.metadata?.explorerData)}
          />
        );
    
      
      case 'visualization':
        return (
          <VisualizationMessage 
            charts={message.metadata?.visualizations}
            onOpenVisualization={() => onAction?.('openVisualization', message.metadata?.visualizations)}
          />
        );
      case 'tool_call':
        return (
          <ToolCallMessage 
            toolCalls={message.metadata?.toolCalls || []}
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
