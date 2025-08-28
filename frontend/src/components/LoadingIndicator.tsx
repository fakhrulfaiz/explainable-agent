import React from 'react';

const LoadingIndicator: React.FC = () => {
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
      </div>
    </div>
  );
};

export default LoadingIndicator;
