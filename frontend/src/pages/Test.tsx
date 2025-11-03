import React, { useState } from 'react';
import { ToolCallMessage } from '../components/messages/ToolCallMessage';
import InputForm from '../components/InputForm';
import TestSidebar from '../components/TestSidebar';

// Mock data for ToolCallRenderer testing
const mockToolCalls = [
  {
    id: '1',
    name: 'search',
    input: {
      query: 'React hooks best practices'
    },
    status: 'approved' as const,
    output: {
      results: [
        { title: 'React Hooks Documentation', url: 'https://react.dev' },
        { title: 'Best Practices Guide', url: 'https://example.com' }
      ]
    }
  },
  {
    id: '2',
    name: 'calculator',
    input: {
      expression: '2 + 2'
    },
    status: 'pending' as const,
    output: null
  },
  {
    id: '3',
    name: 'send_email',
    input: {
      to: 'user@example.com',
      subject: 'Test Email',
      body: 'This is a test email'
    },
    status: 'rejected' as const,
    output: {
      success: false,
      message: 'Email sending failed'
    }
  }
];

const Test: React.FC = () => {
  const [inputValue, setInputValue] = useState('');
  const [usePlanning, setUsePlanning] = useState(false);
  const [useExplainer, setUseExplainer] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | undefined>();
  const [isSidebarExpanded, setIsSidebarExpanded] = useState(true);

  const handleSend = () => {
    console.log('Send clicked:', inputValue);
    alert(`Sending: ${inputValue}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    console.log('Key pressed:', e.key);
  };

  const handleNewThread = () => {
    console.log('New thread clicked');
    setSelectedThreadId(undefined);
  };

  const handleThreadSelect = (threadId: string) => {
    console.log('Thread selected:', threadId);
    setSelectedThreadId(threadId);
  };

  return (
    <div className="h-screen flex bg-gray-50 dark:bg-neutral-800 overflow-hidden">
      {/* TestSidebar */}
      <TestSidebar
        selectedThreadId={selectedThreadId}
        onThreadSelect={handleThreadSelect}
        onNewThread={handleNewThread}
        onExpandedChange={setIsSidebarExpanded}
      />
      
      {/* Main Content */}
      <div className={`flex-1 overflow-y-auto p-8 transition-all duration-300 ${isSidebarExpanded ? 'ml-64' : 'ml-12'}`}>
      <div className="max-w-5xl mx-auto w-full space-y-8">
        <div className="bg-white dark:bg-neutral-700 rounded-lg shadow-md p-6">
          <h1 className="text-2xl font-bold mb-4 text-gray-900 dark:text-gray-100">
            Component Testing Page
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            This page is for testing components in isolation.
          </p>
        </div>

        {/* ToolCallMessage Test Section */}
        <div className="bg-white dark:bg-neutral-700 rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
            ToolCallMessage Component
          </h2>
          <div className="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
            <ToolCallMessage toolCalls={mockToolCalls} />
          </div>
        </div>

        {/* InputForm Test Section */}
        <div className="bg-white dark:bg-neutral-700 rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
            InputForm Component
          </h2>
          <div className="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
            <InputForm
              value={inputValue}
              onChange={setInputValue}
              onSend={handleSend}
              onKeyDown={handleKeyDown}
              placeholder="Test input placeholder..."
              disabled={false}
              isLoading={false}
              usePlanning={usePlanning}
              useExplainer={useExplainer}
              onPlanningToggle={setUsePlanning}
              onExplainerToggle={setUseExplainer}
              onFilesChange={setAttachedFiles}
              attachedFiles={attachedFiles}
            />
          </div>
          <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
            <p>Planning: {usePlanning ? 'Enabled' : 'Disabled'}</p>
            <p>Explainer: {useExplainer ? 'Enabled' : 'Disabled'}</p>
            <p>Attached Files: {attachedFiles.length}</p>
          </div>
        </div>
      </div>
      </div>
    </div>
  );
};

export default Test;
