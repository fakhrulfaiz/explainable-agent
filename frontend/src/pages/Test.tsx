import React, { useState } from 'react';
import { ToolCallMessage } from '../components/messages/ToolCallMessage';
import InputForm from '../components/InputForm';
import TestSidebar from '../components/TestSidebar';
import { UploadedAttachment } from '@/types/attachments';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ExternalLink, FileText, ImageIcon } from 'lucide-react';

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
  const [uploadedAttachments, setUploadedAttachments] = useState<UploadedAttachment[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState<string | undefined>();
  const [isSidebarExpanded, setIsSidebarExpanded] = useState(true);

  const formatFileSize = (bytes: number) => {
    if (!Number.isFinite(bytes) || bytes <= 0) return '—';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.min(
      units.length - 1,
      Math.floor(Math.log(bytes) / Math.log(1024))
    );
    const value = bytes / Math.pow(1024, i);
    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
  };

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
    <div className="h-screen flex bg-background overflow-hidden">
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
        <div className="bg-card rounded-lg shadow-md p-6">
          <h1 className="text-2xl font-bold mb-4 text-card-foreground">
            Component Testing Page
          </h1>
          <p className="text-muted-foreground mb-6">
            This page is for testing components in isolation.
          </p>
        </div>

        {/* ToolCallMessage Test Section */}
        <div className="bg-card rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4 text-card-foreground">
            ToolCallMessage Component
          </h2>
          <div className="border border-border rounded-lg p-4">
            <ToolCallMessage 
              toolCalls={mockToolCalls}
              content={"I'm about to run a couple of tools to fetch results and compute values.\n\n- First I'll search for resources related to React hooks.\n- Then I'll evaluate a simple calculation to confirm the math."}
            />
          </div>
        </div>

        {/* InputForm Test Section */}
        <div className="bg-card rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4 text-card-foreground">
            InputForm Component
          </h2>
          <div className="border border-border rounded-lg p-4">
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
              onAttachmentsUploaded={(files) => {
                setUploadedAttachments((prev) => [...prev, ...files]);
                setUploadError(null);
              }}
              onAttachmentUploadError={(message) => setUploadError(message)}
              onAttachmentDeleted={(attachment) => {
                setUploadedAttachments((prev) =>
                  prev.filter((item) => item.path !== attachment.path)
                );
              }}
            />
            </div>
          
          <div className="mt-4 text-sm text-muted-foreground">
            <p>Planning: {usePlanning ? 'Enabled' : 'Disabled'}</p>
            <p>Explainer: {useExplainer ? 'Enabled' : 'Disabled'}</p>
            <p>Attached Files: {attachedFiles.length}</p>
          </div>
          {uploadError && (
            <div className="mt-4 p-3 rounded-lg border border-destructive text-sm text-destructive bg-destructive/10">
              {uploadError}
            </div>
          )}
          {uploadedAttachments.length > 0 && (
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-card-foreground">Uploaded Attachments</h3>
                <Badge variant="secondary" className="text-xs font-medium">
                  {uploadedAttachments.length} file{uploadedAttachments.length > 1 ? 's' : ''}
                </Badge>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {uploadedAttachments.map((file) => {
                  const isImage = file.type?.startsWith('image/');
                  return (
                    <Card key={file.path} className="flex flex-col">
                      <CardHeader className="space-y-1 pb-3">
                        <CardTitle className="text-sm font-semibold truncate">
                          {file.name}
                        </CardTitle>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{formatFileSize(file.size)}</span>
                          <span>•</span>
                          <span>{file.type || 'Unknown type'}</span>
                        </div>
                      </CardHeader>
                      <CardContent className="pb-3">
                        <div className="rounded-lg border border-border/60 bg-muted/30 overflow-hidden">
                          {isImage ? (
                            <img
                              src={file.url}
                              alt={file.name}
                              className="h-40 w-full object-cover"
                            />
                          ) : (
                            <div className="h-40 w-full flex flex-col items-center justify-center text-muted-foreground text-sm gap-2">
                              <FileText className="w-8 h-8" />
                              <span>Preview unavailable</span>
                            </div>
                          )}
                        </div>
                      </CardContent>
                      <CardFooter className="mt-auto flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1 text-xs text-muted-foreground truncate max-w-[70%]">
                          {isImage ? <ImageIcon className="w-3.5 h-3.5" /> : <FileText className="w-3.5 h-3.5" />}
                          <span className="truncate">{file.url}</span>
                        </div>
                        <Button variant="outline" size="sm" asChild>
                          <a href={file.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1">
                            <ExternalLink className="w-3.5 h-3.5" />
                            View
                          </a>
                        </Button>
                      </CardFooter>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  );
};

export default Test;
