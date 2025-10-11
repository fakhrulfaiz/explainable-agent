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
      className="border border-gray-200 rounded-lg p-4 bg-white hover:bg-gray-50 cursor-pointer transition-colors"
    >
      <div className="font-medium text-gray-900 mb-2">
        <span className="text-purple-600 text-sm font-normal">Visualization: </span>
        {getTitle()}
      </div>
      <div className="text-sm text-gray-500">
        {getSummary()}
      </div>
    </div>
  );
};

export default VisualizationRenderer;


