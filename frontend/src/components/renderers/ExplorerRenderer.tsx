import React from 'react';

interface ExplorerRendererProps {
  data?: any;
  onOpenExplorer?: () => void;
  content?: string;
}

export const ExplorerRenderer: React.FC<ExplorerRendererProps> = ({  
  data, 
  onOpenExplorer, 
  content 
}) => {
  // Create a summary from the data
  const getSummary = () => {
    if (!data) return 'Click to view analysis details';
    
    const parts = [];
    
    if (data.steps && data.steps.length > 0) {
      parts.push(`${data.steps.length} step${data.steps.length !== 1 ? 's' : ''} executed`);
    }
    
    if (data.overall_confidence) {
      parts.push(`${(data.overall_confidence * 100).toFixed(0)}% confidence`);
    }
    
    if (data.run_status) {
      parts.push(`${data.run_status}`);
    }
    
    return parts.length > 0 ? parts.join(' • ') : 'Click to view analysis details';
  };

  // Get the user's question - prioritize data.query, fallback to a default
  const getUserQuestion = () => {
    if (data?.query) {
      return data.query;
    }
    // Don't use content as fallback since it contains the assistant's response
    return 'Analysis Complete';
  };

  return (
    <div 
      onClick={onOpenExplorer}
      className="border border-gray-200 dark:border-neutral-700 rounded-lg p-4 bg-white dark:bg-neutral-800 hover:bg-gray-50 dark:hover:bg-neutral-700 cursor-pointer transition-colors"
    >
      {/* User's Original Question */}
      <div className="font-medium text-gray-900 dark:text-white mb-2 max-w-full">
        <span className="text-blue-600 dark:text-blue-400 text-sm font-normal">Question: </span>
        <span className="truncate block">{getUserQuestion()}</span>
      </div>
      
      {/* Summary in gray text */}
      <div className="text-sm text-gray-500 dark:text-neutral-400">
        {getSummary()}
      </div>
    </div>
  );
};
