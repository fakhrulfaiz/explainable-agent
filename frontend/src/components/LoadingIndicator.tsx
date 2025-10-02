import React from 'react';

interface LoadingIndicatorProps {
  activeTools?: string[];
}

const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({ activeTools }) => {
  return (
    <div className="flex justify-start">
      <div className="bg-gray-100 px-4 py-3 rounded-lg">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
          <div 
            className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" 
            style={{ animationDelay: '0.1s' }}
          ></div>
          <div 
            className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" 
            style={{ animationDelay: '0.2s' }}
          ></div>
          <span className="text-gray-600 text-sm ml-2">Generating...</span>
        </div>
        {activeTools && activeTools.length > 0 && (
          <div className="mt-2 space-y-1">
            {activeTools.map((tool, i) => (
              <div key={i} className="text-xs text-blue-600 flex items-center gap-1">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                Using {tool}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default LoadingIndicator;