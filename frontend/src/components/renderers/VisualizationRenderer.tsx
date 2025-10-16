import React from 'react';

interface VisualizationRendererProps {
  charts?: any[];
  onOpenVisualization?: () => void;
}

export const VisualizationRenderer: React.FC<VisualizationRendererProps> = ({  
  charts, 
  onOpenVisualization,  
}) => {
  const getSummary = () => {
    const count = Array.isArray(charts) ? charts.length : 0;
    if (count === 0) return 'Click to view visualization';
    const types = (charts || [])
      .map((c: any) => c?.type)
      .filter(Boolean)
      .slice(0, 3)
      .join(', ');
    return `${count} chart${count !== 1 ? 's' : ''}${types ? ` • ${types}` : ''}`;
  };

  const getTitle = () => {
    return 'Visualization Ready';
  };

  return (
    <div 
      onClick={onOpenVisualization}
      className="border border-gray-200 dark:border-neutral-700 rounded-lg p-4 bg-white dark:bg-neutral-800 hover:bg-gray-50 dark:hover:bg-neutral-700 cursor-pointer transition-colors"
    >
      <div className="font-medium text-gray-900 dark:text-white mb-2">
        <span className="text-purple-600 dark:text-purple-400 text-sm font-normal">Visualization: </span>
        {getTitle()}
      </div>
      <div className="text-sm text-gray-500 dark:text-neutral-400">
        {getSummary()}
      </div>
    </div>
  );
};

export default VisualizationRenderer;


