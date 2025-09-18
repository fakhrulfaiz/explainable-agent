import { Components } from 'react-markdown';

export const markdownComponents: Components = {
  p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
  ol: ({children}) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
  ul: ({children}) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
  li: ({children}) => <li className="text-inherit">{children}</li>,
  code: ({children}) => <code className="bg-gray-200 px-1 rounded text-sm font-mono">{children}</code>,
  strong: ({children}) => <strong className="font-semibold">{children}</strong>,
  
  
  img: ({src, alt, title}) => (
    <img 
      src={src} 
      alt={alt || ''} 
      title={title}
      className="w-full max-w-full h-auto md:max-w-[500px] lg:max-w-[600px] sm:max-w-[400px] rounded-lg shadow-sm my-4 cursor-pointer hover:opacity-80 transition-opacity"
      onClick={() => window.open(src, '_blank')}
    />
  )
};