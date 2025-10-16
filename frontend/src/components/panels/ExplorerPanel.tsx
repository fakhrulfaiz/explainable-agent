import React, { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import StepDetails, { ExplorerStep } from '../StepDetails';
import '../../styles/scrollbar.css';
import { getStatusDisplayName, getStatusColor } from '../../utils/statusHelpers';
import { markdownComponents } from '../../utils/markdownComponents';
import remarkGfm from 'remark-gfm';
import { useUIState } from '../../contexts/UIStateContext';



export type ExplorerResult = {
  thread_id: string;
  run_status: string;
  assistant_response?: string;
  query?: string;  // User's original question
  plan?: string;
  error?: string | null;
  steps?: ExplorerStep[];
  final_result?: {
    summary?: string;
    details?: string;
    source?: string;
    inference?: string;
    extra_explanation?: string;
  };
  total_time?: number | null;
  overall_confidence?: number;
};

type ExplorerPanelProps = { 
  open: boolean;
  onClose: () => void;
  data: ExplorerResult | null;
  initialWidthPx?: number;
  minWidthPx?: number;
  maxWidthPx?: number;
};

const ExplorerPanel: React.FC<ExplorerPanelProps> = ({ open, onClose, data, initialWidthPx = 620, minWidthPx = 320, maxWidthPx = 1100}) => {
  const { state } = useUIState();
  const { isDarkMode } = state;
  
  // Calculate responsive initial width based on screen size
  const getResponsiveWidth = () => {
    const screenWidth = window.innerWidth;
    if (screenWidth <= 768) { // Mobile breakpoint
      return Math.min(screenWidth - 32, maxWidthPx); // Leave 16px margin on each side
    } else if (screenWidth <= 1024) { // Tablet breakpoint
      return Math.min(screenWidth * 0.8, initialWidthPx); // 80% of screen width or default
    }
    return initialWidthPx; // Desktop uses original default
  };

  const [width, setWidth] = useState<number>(getResponsiveWidth());
  const isResizingRef = useRef<boolean>(false);

  const onMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizingRef.current) return;
    const newWidth = Math.min(Math.max(window.innerWidth - e.clientX, minWidthPx), maxWidthPx);
    setWidth(newWidth);
  }, [minWidthPx, maxWidthPx]);

  // Handle window resize to update panel width responsively
  const handleWindowResize = useCallback(() => {
    if (!isResizingRef.current) { 
      setWidth(getResponsiveWidth());
    }
  }, []);

  const onMouseUp = useCallback(() => {
    isResizingRef.current = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, []);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizingRef.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    window.addEventListener('resize', handleWindowResize);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('resize', handleWindowResize);
    };
  }, [onMouseMove, onMouseUp, handleWindowResize]);

  return (
    <div
        className={`fixed top-0 right-0 h-full bg-white dark:bg-neutral-900 shadow-xl border-l border-gray-200 dark:border-neutral-700 transform transition-transform duration-300 ease-in-out z-40 ${open ? 'translate-x-0' : 'translate-x-full'}`}
        style={{ width }}
      >
        {/* Resize handle - hidden on mobile */}
        <div
          onMouseDown={startResize}
          className="absolute left-0 top-0 h-full w-1 cursor-col-resize bg-transparent hover:bg-gray-200/50 hidden sm:block"
          aria-label="Resize"
        />

        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-900">
          <h3 className="font-semibold text-gray-900 dark:text-white">Agent Explorer</h3>
          <div className="flex items-center gap-2">
            <button 
              onClick={onClose} 
              className="px-3 py-2 rounded bg-gray-200 dark:bg-neutral-700 hover:bg-gray-300 dark:hover:bg-neutral-600 text-gray-800 dark:text-white text-sm sm:text-sm min-h-[36px] touch-manipulation"
              aria-label="Close panel"
            >
              Close
            </button>
          </div>
        </div>

        <div 
          className="p-4 h-[calc(100%-56px)] slim-scroll text-gray-900 dark:text-neutral-200"
          style={{
            overflowY: 'overlay' as any,
            scrollbarWidth: 'thin',
            scrollbarColor: isDarkMode ? '#525252 transparent' : '#d1d5db transparent'
          }}
        >
          {!data ? (
            <div className="text-gray-500 dark:text-neutral-400 text-sm">No data yet. Send a message and open after the result.</div>
          ) : (
            <div className="space-y-4">
            {/* User's Original Question */}
            {data.query && (
              <div className="p-3 bg-blue-50 dark:bg-neutral-800 rounded border border-blue-200 dark:border-neutral-700">
                <div className="text-sm text-blue-800 dark:text-blue-400 font-medium mb-1">Your Question</div>
                <div className="text-gray-700 dark:text-neutral-200 text-sm font-medium">
                  {data.query}
                </div>
              </div>
            )}

            {/* Summary */}
            <details className="border border-green-200 dark:border-neutral-700 rounded bg-green-50 dark:bg-neutral-800">
              <summary className="list-none cursor-pointer select-none p-3 flex items-center justify-between hover:bg-green-100 dark:hover:bg-neutral-700">
                <div className="text-sm text-gray-800 dark:text-neutral-200 font-medium">Summary</div>
                <span className="text-xs text-gray-500 dark:text-neutral-400">Click to expand</span>
              </summary>
              <div className="p-3 border-t border-green-200 dark:border-neutral-700 text-gray-700 dark:text-neutral-200 text-sm">
                {data.final_result?.summary || data.assistant_response ? (
                  <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>
                    {data.final_result?.summary || data.assistant_response || ''}
                  </ReactMarkdown>
                ) : '—'}
              </div>
            </details>

            {/* Plan */}
            {data.plan && (
              <details className="border border-blue-200 dark:border-neutral-700 rounded bg-blue-50 dark:bg-neutral-800">
                <summary className="list-none cursor-pointer select-none p-3 flex items-center justify-between hover:bg-blue-100 dark:hover:bg-neutral-700">
                  <div className="text-base text-gray-800 dark:text-neutral-200 font-medium">Plan</div>
                  <span className="text-sm text-gray-500 dark:text-neutral-400">Click to expand</span>
                </summary>
                <div className="p-3 border-t border-blue-200 dark:border-neutral-700 text-sm text-gray-700 dark:text-neutral-200">
                  <ReactMarkdown components={markdownComponents}>
                    {data.plan}
                  </ReactMarkdown>
                </div>
              </details>
            )}

            {/* Details */}
            {data.final_result?.details && (
              <div className="p-3 bg-gray-50 dark:bg-neutral-800 rounded border border-gray-200 dark:border-neutral-700">
                <div className="text-base text-gray-800 dark:text-neutral-200 font-medium mb-1">Details</div>
                <div className="text-sm text-gray-700 dark:text-neutral-200">
                  <ReactMarkdown components={markdownComponents}>
                    {data.final_result.details}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {/* Steps */}
            <StepDetails steps={data.steps || []} />

            {/* Meta */}
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-700 dark:text-neutral-200">
              <div className="p-2 bg-gray-50 dark:bg-neutral-800 rounded border border-gray-200 dark:border-neutral-700">
                <div className="text-gray-500 dark:text-neutral-400">Execution Status</div>
                <div className={`font-medium px-2 py-1 rounded text-xs ${getStatusColor(data.run_status)}`}>
                  {getStatusDisplayName(data.run_status)}
                </div>
              </div>
              <div className="p-2 bg-gray-50 dark:bg-neutral-800 rounded border border-gray-200 dark:border-neutral-700">
                <div className="text-gray-500 dark:text-neutral-400">Confidence</div>
                <div className="font-medium">{typeof data.overall_confidence === 'number' ? `${(data.overall_confidence * 100).toFixed(0)}%` : '—'}</div>
              </div>
              <div className="p-2 bg-gray-50 dark:bg-neutral-800 rounded border border-gray-200 dark:border-neutral-700">
                <div className="text-gray-500 dark:text-neutral-400">Total time</div>
                <div className="font-medium">{typeof data.total_time === 'number' ? `${data.total_time.toFixed(2)}s` : '—'}</div>
              </div>
              <div className="p-2 bg-gray-50 dark:bg-neutral-800 rounded border border-gray-200 dark:border-neutral-700">
                <div className="text-gray-500 dark:text-neutral-400">Thread</div>
                <div className="font-medium">{data.thread_id}...</div>
              </div>
            </div>
            </div>
          )}
        </div>
      </div>
  );
};

export default ExplorerPanel;


