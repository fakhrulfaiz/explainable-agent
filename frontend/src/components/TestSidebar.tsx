import React, { useState } from 'react';
import { PanelLeftClose, PanelLeftOpen, Plus, Search, MessageSquare, Calendar, Settings } from 'lucide-react';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { Input } from './ui/input';

interface TestSidebarProps {
  selectedThreadId?: string;
  onThreadSelect?: (threadId: string) => void;
  onNewThread?: () => void;
  onExpandedChange?: (isExpanded: boolean) => void;
}

const TestSidebar: React.FC<TestSidebarProps> = ({
  selectedThreadId,
  onThreadSelect,
  onNewThread,
  onExpandedChange
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  const toggleExpanded = () => {
    const newState = !isExpanded;
    setIsExpanded(newState);
    onExpandedChange?.(newState);
  };

  // Mock threads data
  const mockThreads = [
    { id: '1', title: 'Chat about React', lastMessage: 'How do hooks work?', updatedAt: '2024-01-15' },
    { id: '2', title: 'Python Questions', lastMessage: 'What is a decorator?', updatedAt: '2024-01-14' },
    { id: '3', title: 'TypeScript Tips', lastMessage: 'Generics explained', updatedAt: '2024-01-13' },
  ];

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
  };

  const filteredThreads = mockThreads.filter(thread =>
    thread.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    thread.lastMessage.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const sidebarWidth = isExpanded ? 'w-64' : 'w-14';

  return (
    <aside
      className={`fixed left-0 top-0 h-screen bg-gray-50 dark:bg-neutral-800 border-r border-gray-200 dark:border-neutral-700 transition-[width] duration-300 ease-in-out z-40 ${sidebarWidth} flex flex-col overflow-hidden`}
    >
      {/* Header */}
      <div className="p-2 space-y-1 border-b border-gray-200 dark:border-neutral-700 overflow-hidden">
        {/* Toggle Button */}
        <button
          onClick={toggleExpanded}
          className="w-full h-10 flex items-center pl-3 hover:bg-gray-100 dark:hover:bg-neutral-700 rounded-md transition-colors"
        >
          {isExpanded ? (
            <PanelLeftClose className="h-5 w-5 flex-shrink-0" />
          ) : (
            <PanelLeftOpen className="h-5 w-5 flex-shrink-0" />
          )}
          {isExpanded && (
            <span className="ml-3 font-semibold whitespace-nowrap overflow-hidden">
              Explainable Agent
            </span>
          )}
        </button>

        {/* New Thread Button */}
        <button
          onClick={onNewThread}
          className="w-full h-10 flex items-center pl-2.5 hover:bg-gray-100 dark:hover:bg-neutral-700 rounded-md transition-colors"
        >
          <Plus className="h-5 w-5 flex-shrink-0" />
          {isExpanded && (
            <span className="ml-3 font-medium whitespace-nowrap overflow-hidden">
              New Thread
            </span>
          )}
        </button>
      </div>

      {/* Search Bar - only show when expanded */}
      {isExpanded && (
        <div className="p-3 border-b border-gray-200 dark:border-neutral-700">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-neutral-400" />
            <Input
              type="text"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 bg-white dark:bg-neutral-800 border-gray-300 dark:border-neutral-600"
            />
          </div>
        </div>
      )}

      {/* Threads List */}
      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full">
          {isExpanded ? (
            filteredThreads.length === 0 ? (
              <div className="p-4 text-center text-gray-500 dark:text-neutral-400 text-sm">
                {searchQuery ? 'No matching threads' : 'No chat threads found'}
              </div>
            ) : (
              <div className="space-y-1 py-2 px-2">
                {filteredThreads.map((thread) => (
                  <div
                    key={thread.id}
                    onClick={() => onThreadSelect?.(thread.id)}
                    className={`p-3 rounded-lg cursor-pointer transition-colors ${
                      selectedThreadId === thread.id
                        ? 'bg-gray-100 dark:bg-neutral-800'
                        : 'hover:bg-gray-50 dark:hover:bg-neutral-800'
                    }`}
                  >
                    <div className="font-medium text-sm truncate mb-1 text-gray-900 dark:text-white">
                      <MessageSquare className="w-3 h-3 inline mr-2" />
                      {thread.title}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-neutral-400 truncate mb-1">
                      {thread.lastMessage}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-neutral-500">
                      <Calendar className="w-3 h-3" />
                      {formatDate(thread.updatedAt)}
                    </div>
                  </div>
                ))}
              </div>
            )
          ) : null}
        </ScrollArea>
      </div>

      {/* Footer */}
      <div className="p-2 border-t border-gray-200 dark:border-neutral-700 overflow-hidden">
        <button
          className="w-full h-10 flex items-center pl-3 hover:bg-gray-100 dark:hover:bg-neutral-700 rounded-md transition-colors"
          title={!isExpanded ? "Settings" : undefined}
        >
          <Settings className="w-4 h-4 flex-shrink-0" />
          {isExpanded && (
            <span className="ml-2 text-xs font-medium whitespace-nowrap overflow-hidden">
              Settings
            </span>
          )}
        </button>
      </div>
    </aside>
  );
};

export default TestSidebar;