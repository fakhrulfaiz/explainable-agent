import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Message, ContentBlock, isTextBlock, isToolCallsBlock, isExplorerBlock, isVisualizationsBlock } from '../types/chat';
import { ExplorerMessage } from './messages/ExplorerMessage';
import { markdownComponents } from '../utils/markdownComponents';
import VisualizationMessage from './messages/VisualizationMessage';
import { ToolCallMessage } from './messages/ToolCallMessage';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface MessageRendererProps {
  message: Message;
  onAction?: (action: string, data?: any) => void;
}

interface SequentialToolCallsRendererProps {
  blocks: ContentBlock[];
  sequentialIndices: number[];
  renderContentBlock: (block: ContentBlock) => React.ReactNode;
}

const SequentialToolCallsRenderer: React.FC<SequentialToolCallsRendererProps> = ({ 
  blocks, 
  sequentialIndices, 
  renderContentBlock 
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Get all tool names from sequential blocks
  const toolNames: string[] = [];
  sequentialIndices.forEach(index => {
    const block = blocks[index];
    if (isToolCallsBlock(block)) {
      block.data.toolCalls.forEach((tc: any) => {
        toolNames.push(tc.name);
      });
    }
  });
  
  // Group blocks: sequential tool_calls vs others
  const sequentialStart = Math.min(...sequentialIndices);
  const sequentialEnd = Math.max(...sequentialIndices);
  
  const beforeBlocks = blocks.slice(0, sequentialStart);
  const sequentialBlocks = blocks.slice(sequentialStart, sequentialEnd + 1);
  const afterBlocks = blocks.slice(sequentialEnd + 1);
  
  return (
    <div className="content-blocks">
      {/* Blocks before sequential tool calls */}
      {beforeBlocks.map((block) => renderContentBlock(block))}
      
      {/* Collapsible wrapper for sequential tool calls */}
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger asChild>
          <button
            className="w-full flex items-center gap-2 p-2 mb-2 rounded-lg border border-border bg-background hover:bg-accent hover:text-accent-foreground transition-colors text-left"
            type="button"
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 flex-shrink-0 transition-transform duration-200" />
            ) : (
              <ChevronRight className="w-4 h-4 flex-shrink-0 transition-transform duration-200" />
            )}
            <span className="font-semibold text-foreground">
              {toolNames.length} tools executed
            </span>
          </button>
        </CollapsibleTrigger>
        
        {!isExpanded && (
          <div className="mb-2 ml-6 space-y-1 animate-in fade-in-0 duration-200">
            <ul className="list-disc list-inside space-y-0.5">
              {toolNames.map((name, index) => (
                <li key={index} className="text-sm text-muted-foreground">
                  {name}
                </li>
              ))}
            </ul>
          </div>
        )}
        
        <CollapsibleContent className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:slide-out-to-top-2 data-[state=open]:slide-in-from-top-2 duration-200">
          <div className="pt-2">
            {sequentialBlocks.map((block) => renderContentBlock(block))}
          </div>
        </CollapsibleContent>
      </Collapsible>
      
      {/* Blocks after sequential tool calls */}
      {afterBlocks.map((block) => renderContentBlock(block))}
    </div>
  );
};

export const MessageRenderer: React.FC<MessageRendererProps> = ({ message, onAction }) => {
  const renderContentBlock = (block: ContentBlock) => {
    if (isTextBlock(block)) {
      return (
        <div key={block.id} className="content-block text-block">
          <ReactMarkdown 
            components={markdownComponents}
            remarkPlugins={[remarkGfm]}
          >
            {block.data.text}
          </ReactMarkdown>
        </div>
      );
    }
    
    if (isToolCallsBlock(block)) {
      const mappedToolCalls = block.data.toolCalls.map(toolCall => ({
        id: toolCall.name,
        name: toolCall.name,
        input: toolCall.input,
        output: toolCall.output,
        status: toolCall.status
      }));
      
      return (
        <div key={block.id} className="content-block tool-calls-block mb-4">
          <ToolCallMessage 
            toolCalls={mappedToolCalls}
            content={block.data.content}
          />
        </div>
      );
    }
    
    if (isExplorerBlock(block)) {
      return (
        <div key={block.id} className="content-block explorer-block mb-4">
          <ExplorerMessage 
            checkpointId={block.data.checkpointId}
            data={block.data.explorerData}
            onOpenExplorer={() => onAction?.('openExplorer', { checkpointId: block.data.checkpointId, data: block.data.explorerData })}
          />
        </div>
      );
    }
    
    if (isVisualizationsBlock(block)) {
      return (
        <div key={block.id} className="content-block visualizations-block mb-4">
          <VisualizationMessage 
            checkpointId={block.data.checkpointId}
            charts={block.data.visualizations}
            onOpenVisualization={() => onAction?.('openVisualization', { checkpointId: block.data.checkpointId, charts: block.data.visualizations })}
          />
        </div>
      );
    }
    
    return null;
  };

  const renderContent = () => {
    // Content is always an array of content blocks
    const contentBlocks = message.content || [];
    
    // Handle empty content
    if (!contentBlocks || contentBlocks.length === 0) {
      return null;
    }
    
    // Filter out tool_explanation text blocks if tool_calls block already has the content
    // This prevents duplication while still allowing real-time streaming
    const toolCallsBlock = contentBlocks.find((b: ContentBlock) => b.type === 'tool_calls');
    const toolCallsContent = toolCallsBlock ? (toolCallsBlock.data as any).content : null;
    
    // Filter: hide text blocks that appear before tool_calls block and match tool_calls content
    // This hides tool_explanation text while keeping the final response text
    const filteredBlocks = toolCallsContent
      ? contentBlocks.filter((block, index) => {
          if (block.type === 'text') {
            const textContent = (block.data as any).text || '';
            const toolCallsIndex = contentBlocks.findIndex((b: ContentBlock) => b.type === 'tool_calls');
            
            // Hide text block if:
            // 1. It appears before tool_calls block
            // 2. Its content matches or is contained in tool_calls block content
            if (index < toolCallsIndex && toolCallsContent && textContent.trim()) {
              const normalizedText = textContent.trim();
              const normalizedToolContent = toolCallsContent.trim();
              // Check if text content matches tool_calls content (tool explanation)
              if (normalizedToolContent.includes(normalizedText) || normalizedText === normalizedToolContent) {
                return false; // Hide this text block (it's the tool explanation)
              }
            }
          }
          return true;
        })
      : contentBlocks;
    
    // Detect sequential tool_calls blocks
    const sequentialToolCallsBlocks: number[] = [];
    let currentSequence: number[] = [];
    
    filteredBlocks.forEach((block, index) => {
      if (isToolCallsBlock(block)) {
        currentSequence.push(index);
      } else {
        if (currentSequence.length >= 2) {
          sequentialToolCallsBlocks.push(...currentSequence);
        }
        currentSequence = [];
      }
    });
    
    // Don't forget the last sequence
    if (currentSequence.length >= 2) {
      sequentialToolCallsBlocks.push(...currentSequence);
    }
    
    const hasSequentialToolCalls = sequentialToolCallsBlocks.length >= 2;
    
    // If we have sequential tool_calls blocks, wrap them in a collapsible
    if (hasSequentialToolCalls) {
      return <SequentialToolCallsRenderer blocks={filteredBlocks} sequentialIndices={sequentialToolCallsBlocks} renderContentBlock={renderContentBlock} />;
    }
    
    return (
      <div className="content-blocks">
        {filteredBlocks.map((block) => renderContentBlock(block))}
      </div>
    );
  };

  return (
    <div className="message-content">
      {renderContent()}
    </div>
  );
};
