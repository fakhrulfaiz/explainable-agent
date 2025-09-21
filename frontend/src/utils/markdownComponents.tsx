import { Components } from 'react-markdown';

export const markdownComponents: Components = {
  p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
  ol: ({children}) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
  ul: ({children}) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
  li: ({children}) => <li className="text-inherit">{children}</li>,
  code: ({children}) => <code className="bg-gray-200 px-1 rounded text-sm font-mono">{children}</code>,
  strong: ({children}) => <strong className="font-semibold">{children}</strong>,
  a: ({href, children}) => (
    <a 
      href={href} 
      target="_blank" 
      rel="noopener noreferrer"
      className="text-blue-600 hover:text-blue-800 underline"
    >
      {children}
    </a>
  ),
  img: ({src, alt, title}) => (
    <img 
      src={src} 
      alt={alt || ''} 
      title={title}
      className="w-full max-w-full h-auto md:max-w-[500px] lg:max-w-[600px] sm:max-w-[400px] rounded-lg shadow-sm my-4 cursor-pointer hover:opacity-80 transition-opacity"
      onClick={() => window.open(src, '_blank')}
    />
  ),
  // Table components for markdown tables
  table: ({children}) => (
    <div className="overflow-x-auto my-4">
      <table className="min-w-full border border-gray-300 rounded-lg overflow-hidden">
        {children}
      </table>
    </div>
  ),
  thead: ({children}) => (
    <thead className="bg-gray-50">
      {children}
    </thead>
  ),
  tbody: ({children}) => (
    <tbody className="bg-white divide-y divide-gray-200">
      {children}
    </tbody>
  ),
  tr: ({children}) => (
    <tr className="hover:bg-gray-50">
      {children}
    </tr>
  ),
  th: ({children}) => (
    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-300">
      {children}
    </th>
  ),
  td: ({children}) => (
    <td className="px-4 py-3 text-sm text-gray-900 border-b border-gray-200">
      {children}
    </td>
  )
};