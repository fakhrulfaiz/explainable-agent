import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { markdownComponents } from '../../utils/markdownComponents';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Check, X, Clock } from 'lucide-react';

type ToolCallStatus = 'pending' | 'approved' | 'rejected';

interface ToolCallInput {
  query?: string;
  expression?: string;
  to?: string;
  subject?: string;
  body?: string;
  [key: string]: any;
}

interface ToolCallOutput {
  results?: Array<{ title: string; url: string }>;
  result?: number;
  success?: boolean;
  message?: string;
  [key: string]: any;
}

interface ToolCall {
  id: string;
  name: string;
  input: ToolCallInput;
  status: ToolCallStatus;
  output?: ToolCallOutput | string | null;
}

interface ToolCallMessageProps {
  toolCalls: ToolCall[];
  content?: string;
}

export const ToolCallMessage: React.FC<ToolCallMessageProps> = ({ toolCalls, content }) => {
  const getStatusColor = (status: ToolCallStatus): string => {
    switch (status) {
      case 'approved':
        return 'text-green-600 dark:text-green-400';
      case 'rejected':
        return 'text-red-600 dark:text-red-400';
      default:
        return 'text-yellow-600 dark:text-yellow-400';
    }
  };

  const getStatusIcon = (status: ToolCallStatus) => {
    switch (status) {
      case 'approved':
        return <Check className="w-4 h-4" />;
      case 'rejected':
        return <X className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const formatContent = (content: any): string => {
    if (typeof content === 'string') {
      return content;
    }
    return `\`\`\`json\n${JSON.stringify(content, null, 2)}\n\`\`\``;
  };

  return (
    <>
      {content && (
        <div className="mb-3 prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        </div>
      )}
      <Accordion type="single" collapsible className="space-y-2">
      {toolCalls.map((call) => (
        <AccordionItem
          key={call.id}
          value={call.id}
          className="border border-gray-200 dark:border-neutral-700 !border-b rounded-lg px-3 bg-white dark:bg-neutral-800 shadow-sm"
        >
            <AccordionTrigger className="hover:no-underline py-2.5">
              <div className="flex items-center gap-3 w-full">
                <div className={`${getStatusColor(call.status)}`}>
                  {getStatusIcon(call.status)}
                </div>
                <div className="flex-1 text-left">
                  <div className="font-semibold text-gray-900 dark:text-gray-100">
                    Call: {call.name}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400 capitalize">
                    {call.status}
                  </div>
                </div>
              </div>
            </AccordionTrigger>
            
            <AccordionContent className="pb-2">
              <div className="space-y-3 pt-1.5">
                <div>
                  <h3 className="font-semibold text-sm text-gray-700 dark:text-gray-300 mb-1.5">
                    Input:
                  </h3>
                  <div className="bg-slate-800 dark:bg-neutral-900 text-slate-50 dark:text-neutral-100 p-2 rounded text-sm overflow-x-auto prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {formatContent(call.input)}
                    </ReactMarkdown>
                  </div>
                </div>

                {call.output && (
                  <div>
                    <h3 className="font-semibold text-sm text-gray-700 dark:text-gray-300 mb-1.5">
                      Output:
                    </h3>
                    <div className={`p-2 rounded text-sm overflow-x-auto prose prose-sm dark:prose-invert max-w-none ${
                      call.status === 'approved' 
                        ? 'bg-green-50 dark:bg-green-900/20 text-green-900 dark:text-green-100' 
                        : call.status === 'rejected'
                        ? 'bg-red-50 dark:bg-red-900/20 text-red-900 dark:text-red-100'
                        : 'bg-slate-800 dark:bg-neutral-900 text-slate-50 dark:text-neutral-100'
                    }`}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {formatContent(call.output)}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}
              </div>
            </AccordionContent>
        </AccordionItem>
      ))}
      </Accordion>
    </>
  );
};


