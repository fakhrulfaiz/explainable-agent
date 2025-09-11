import { Components } from 'react-markdown';

export const markdownComponents: Components = {
  p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
  ol: ({children}) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
  ul: ({children}) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
  li: ({children}) => <li className="text-inherit">{children}</li>,
  code: ({children}) => <code className="bg-gray-200 px-1 rounded text-sm font-mono">{children}</code>,
  strong: ({children}) => <strong className="font-semibold">{children}</strong>
};
