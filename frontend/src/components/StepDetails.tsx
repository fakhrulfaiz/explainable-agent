import React from 'react';
import '../styles/scrollbar.css';

export type ExplorerStep = {
  id: number;
  type: string;
  decision?: string;
  reasoning?: string;
  input?: string;
  output?: string;
  confidence?: number;
  why_chosen?: string;
  timestamp?: string;
};

interface StepDetailsProps {
  steps: ExplorerStep[];
  className?: string;
}

const StepDetails: React.FC<StepDetailsProps> = ({ steps, className = '' }) => {
  if (!Array.isArray(steps) || steps.length === 0) {
    return null;
  }

  return (
    <div className={className}>
      <div className="text-base text-gray-800 font-medium mb-2">Steps</div>
      <div className="space-y-3">
        {steps.map((s) => (
          <details key={s.id} className="border border-gray-200 rounded">
            <summary className="list-none cursor-pointer select-none p-3 flex items-center justify-between hover:bg-gray-50">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center w-6 h-6 text-xs font-semibold rounded-full bg-gray-200 text-gray-700">
                  {s.id}
                </span>
                <span className="font-medium text-gray-800 text-base">{s.type}</span>
              </div>
              <div className="flex items-center gap-2">
                {typeof s.confidence === 'number' ? (
                  <span className="text-sm text-green-700 bg-green-100 px-2 py-0.5 rounded">
                    {(s.confidence * 100).toFixed(0)}%
                  </span>
                ) : (
                  <span className="text-sm text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                    No confidence
                  </span>
                )}
                <span className="text-sm text-gray-500">
                  {s.timestamp ? new Date(s.timestamp).toLocaleTimeString('en-MY', { timeZone: 'Asia/Kuala_Lumpur' }) : ''}
                </span>
              </div>
            </summary>
            <div className="p-3 border-t border-gray-200 space-y-2">
              {s.decision ? (
                <div className="text-base text-gray-700">{s.decision}</div>
              ) : (
                <div className="text-base text-gray-500 italic">No decision provided</div>
              )}
              {s.reasoning ? (
                <div className="text-sm text-gray-600">{s.reasoning}</div>
              ) : (
                <div className="text-sm text-gray-500 italic">No reasoning provided</div>
              )}
              {s.input && (
                <div>
                  <div className="text-sm text-gray-500 mb-1">Input</div>
                  <pre className="text-sm bg-gray-50 border rounded p-2 overflow-x-auto whitespace-pre-wrap text-gray-700 slim-scroll-x">
                    {s.input}
                  </pre>
                </div>
              )}
              {s.output && (
                <div>
                  <div className="text-sm text-gray-500 mb-1">Output</div>
                  <pre className="text-sm bg-gray-50 border rounded p-2 overflow-x-auto whitespace-pre-wrap text-gray-700 slim-scroll-x">
                    {s.output}
                  </pre>
                </div>
              )}
              {s.why_chosen ? (
                <div className="text-sm text-gray-600">Why: {s.why_chosen}</div>
              ) : (
                <div className="text-sm text-gray-500 italic">No explanation provided</div>
              )}
              {s.timestamp && (
                <div className="text-[11px] text-gray-500">
                  {new Date(s.timestamp).toLocaleString('en-MY', { timeZone: 'Asia/Kuala_Lumpur' })}
                </div>
              )}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
};

export default StepDetails;
