import React, { useState, useEffect } from 'react';
import { PanelLeftClose, PanelLeftOpen, Plus, Search, MessageSquare, Settings, MoreVertical, Trash2, Edit, ChevronDown, LogOut } from 'lucide-react';
import { ChatHistoryService, ChatThreadSummary } from '../api/services/chatHistoryService';
import { ScrollArea } from './ui/scroll-area';
import { Button } from './ui/button';
import { Input } from './ui/input';
import DeleteThreadDialog from './DeleteThreadDialog';
import DarkModeToggle from './DarkModeToggle';
import { useAuth } from '@/contexts/AuthContext';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

// Hook to detect mobile viewport
const useIsMobile = () => {
  // Initialize with actual value if available (SSR-safe)
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth < 768; // md breakpoint is 768px
    }
    return false;
  });

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    // Check on mount in case window size changed
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  return isMobile;
};

interface EnhancedSidebarProps {
  selectedThreadId?: string;
  onThreadSelect?: (threadId: string | null) => void;
  onNewThread?: () => void;
  onExpandedChange?: (isExpanded: boolean) => void;
}

const EnhancedSidebar2: React.FC<EnhancedSidebarProps> = ({
  selectedThreadId,
  onThreadSelect,
  onNewThread,
  onExpandedChange
}) => {
  const isMobile = useIsMobile();
  const [isExpanded, setIsExpanded] = useState(true); // Start expanded by default
  const [hasInitialized, setHasInitialized] = useState(false);
  const [threads, setThreads] = useState<ChatThreadSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteDialog, setDeleteDialog] = useState<{ isOpen: boolean; threadId: string; threadTitle: string }>({
    isOpen: false,
    threadId: '',
    threadTitle: ''
  });
  const { user, signOut } = useAuth();
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Initialize sidebar state on mount: collapsed on mobile, expanded on desktop
  useEffect(() => {
    if (!hasInitialized && typeof window !== 'undefined') {
      setIsExpanded(!isMobile);
      setHasInitialized(true);
    }
  }, [isMobile, hasInitialized]);

  // Load threads on mount and when expanded
  useEffect(() => {
    if (threads.length === 0) {
      loadThreads();
    }
  }, []);

  const loadThreads = async () => {
    try {
      setLoading(true);
      setError(null);
      const { threads: fetchedThreads } = await ChatHistoryService.getAllThreads(50, 0);
      setThreads(fetchedThreads);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load threads');
      console.error('Error loading threads:', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpanded = () => {
    const newState = !isExpanded;
    setIsExpanded(newState);
    onExpandedChange?.(newState);
  };

  const handleThreadSelect = (threadId: string) => {
    onThreadSelect?.(threadId);
    // Close sidebar on mobile when thread is selected
    if (isMobile) {
      setIsExpanded(false);
      onExpandedChange?.(false);
    }
  };

  const handleNewThread = () => {
    onNewThread?.();
    // Close sidebar on mobile when new thread is created
    if (isMobile) {
      setIsExpanded(false);
      onExpandedChange?.(false);
    }
  };

  const handleDeleteThread = (threadId: string, threadTitle: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setDeleteDialog({
      isOpen: true,
      threadId,
      threadTitle: threadTitle || 'Untitled Chat'
    });
  };

  const handleConfirmDelete = async () => {
    try {
      await ChatHistoryService.deleteThread(deleteDialog.threadId);
      setThreads(prev => prev.filter(t => t.thread_id !== deleteDialog.threadId));
      
      if (selectedThreadId === deleteDialog.threadId) {
        onThreadSelect?.(null);
      }
      
      setDeleteDialog({ isOpen: false, threadId: '', threadTitle: '' });
    } catch (err) {
      console.error('Error deleting thread:', err);
      alert('Failed to delete thread');
    }
  };

  const handleCancelDelete = () => {
    setDeleteDialog({ isOpen: false, threadId: '', threadTitle: '' });
  };

  const handleEditTitle = (threadId: string, currentTitle: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditingTitle(threadId);
    setNewTitle(currentTitle || 'Untitled Chat');
  };

  const handleSaveTitle = async (threadId: string) => {
    if (!newTitle.trim()) return;

    try {
      await ChatHistoryService.updateThreadTitle(threadId, newTitle.trim());
      setThreads(prev => prev.map(t => 
        t.thread_id === threadId 
          ? { ...t, title: newTitle.trim() }
          : t
      ));
      setEditingTitle(null);
      setNewTitle('');
    } catch (err) {
      console.error('Error updating title:', err);
      alert('Failed to update title');
    }
  };

  const handleCancelEdit = () => {
    setEditingTitle(null);
    setNewTitle('');
  };

  const getDateGroup = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'today';
    if (diffDays === 1) return 'yesterday';
    return 'older';
  };

  const groupThreadsByDate = (threads: ChatThreadSummary[]) => {
    const grouped: { [key: string]: ChatThreadSummary[] } = {
      today: [],
      yesterday: [],
      older: []
    };

    threads.forEach(thread => {
      const group = getDateGroup(thread.updated_at);
      grouped[group].push(thread);
    });

    return grouped;
  };

  const filteredThreads = threads.filter(thread =>
    thread.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    thread.last_message?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const groupedThreads = groupThreadsByDate(filteredThreads);

  // Determine sidebar width and behavior based on mobile/desktop
  const getSidebarClasses = () => {
    if (isMobile) {
      // Mobile: overlay-style when expanded
      if (isExpanded) {
        return 'w-96 opacity-100';
      } else {
        return 'w-0 opacity-0';
      }
    } else {
      // Desktop: fixed sidebar with width transition
      return isExpanded ? 'w-82' : 'w-14';
    }
  };

  return (
    <>
      {/* Mobile: Button to open sidebar when collapsed */}
      {isMobile && !isExpanded && (
        <Button
          variant="ghost"
          size="icon"
          onClick={(e) => {
            e.stopPropagation();
            toggleExpanded();
          }}
          className="fixed top-4 left-4 z-50 hover:bg-gray-100 dark:hover:bg-neutral-700 w-10 h-10 focus:outline-none focus-visible:ring-0 bg-white dark:bg-neutral-800 border border-gray-200 dark:border-neutral-700 shadow-sm"
          title="Open sidebar"
        >
          <PanelLeftOpen className="h-4 w-4" />
        </Button>
      )}

      {/* Mobile: Overlay when expanded */}
      {isMobile && isExpanded && (
        <div
          className="fixed inset-0 bg-black/20 z-40"
          onClick={toggleExpanded}
        />
      )}

      {/* Sidebar */}
      <aside
       className={`fixed left-0 top-0 h-[100dvh] bg-gray-50 dark:bg-neutral-800 border-r border-gray-200 dark:border-neutral-700 transition-all duration-300 ease-in-out z-50 ${getSidebarClasses()} flex flex-col overflow-hidden`}
      >
        <div className={`flex flex-col h-full ${isMobile && isExpanded ? 'w-96 max-w-96' : isMobile ? 'w-0' : 'w-full'} overflow-hidden`}>
          {/* Header */}
          <div className="p-2 space-y-1 border-b border-gray-200 dark:border-neutral-700 overflow-hidden">
          {/* Toggle Button */}
          <button
            onClick={toggleExpanded}
            className="w-full h-10 flex items-center pl-3 hover:bg-gray-100 dark:hover:bg-neutral-700 rounded-md transition-colors"
            title={!isExpanded ? "Expand sidebar" : "Collapse sidebar"}
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
            onClick={handleNewThread}
            className="w-full h-10 flex items-center pl-3 hover:bg-gray-100 dark:hover:bg-neutral-700 rounded-md transition-colors"
            title={!isExpanded ? "New Thread" : undefined}
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
        <div className="flex-1 overflow-hidden min-w-0">
          <ScrollArea className="h-full w-full">
            {isExpanded ? (
              loading ? (
                <div className="p-4 text-center text-gray-500 dark:text-neutral-400 text-sm">
                  Loading threads...
                </div>
              ) : error ? (
                <div className="p-4 text-center text-red-500 text-sm">
                  {error}
                  <Button 
                    onClick={loadThreads}
                    variant="link"
                    className="block mx-auto mt-2 text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
                  >
                    Retry
                  </Button>
                </div>
              ) : filteredThreads.length === 0 ? (
                <div className="p-4 text-center text-gray-500 dark:text-neutral-400 text-sm">
                  {searchQuery ? 'No matching threads' : 'No chat threads found'}
                </div>
              ) : (
                <div className="space-y-1 py-2 px-2 min-w-0 max-w-80">
                  {/* Today Section */}
                  {groupedThreads.today.length > 0 && (
                    <>
                      <div className="px-3 py-2">
                        <div className="text-xs font-semibold text-gray-500 dark:text-neutral-400 uppercase tracking-wider">Today</div>
                      </div>
                      {groupedThreads.today.map((thread) => (
                    <div
                      key={thread.thread_id}
                      className={`relative group rounded-lg transition-colors min-w-0 ${
                        selectedThreadId === thread.thread_id 
                          ? 'bg-gray-100 dark:bg-neutral-700' 
                          : 'hover:bg-gray-50 dark:hover:bg-neutral-600'
                      }`}
                    >
                      <div
                        onClick={() => handleThreadSelect(thread.thread_id)}
                        className="flex items-start gap-2 p-3 cursor-pointer min-w-0 relative"
                      >
                        <div className="min-w-0 flex-1 overflow-hidden group-hover:pr-10">
                          {editingTitle === thread.thread_id ? (
                            <div className="flex items-center gap-2 min-w-0" onClick={(e) => e.stopPropagation()}>
                              <Input
                                type="text"
                                value={newTitle}
                                onChange={(e) => setNewTitle(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    handleSaveTitle(thread.thread_id);
                                  } else if (e.key === 'Escape') {
                                    handleCancelEdit();
                                  }
                                }}
                                onBlur={() => handleSaveTitle(thread.thread_id)}
                                className="flex-1 h-7 text-sm bg-white border-gray-300 text-gray-900 dark:bg-neutral-700 dark:text-white min-w-0 max-w-full"
                                autoFocus
                              />
                            </div>
                          ) : (
                            <>
                              <div className="font-medium text-sm text-gray-900 dark:text-white min-w-0 flex items-center">
                                <MessageSquare className="w-3 h-3 mr-2 flex-shrink-0" />
                                <span className="flex-1 truncate min-w-0">{thread.title || 'Untitled Chat'}</span>
                              </div>
                              {thread.last_message && (
                                <div className="text-xs text-gray-500 dark:text-neutral-400 truncate whitespace-nowrap mt-0.5 min-w-0 flex-1">
                                  {thread.last_message}
                                </div>
                              )}
                            </>
                          )}
                        </div>

                        {/* Actions Button using shadcn DropdownMenu - only show on hover */}
                        {editingTitle !== thread.thread_id && (
                          <div className="absolute right-3 top-3 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <button
                                  className="p-1.5 hover:bg-gray-200 dark:hover:bg-neutral-700 rounded transition-all flex-shrink-0 w-8 h-8 flex items-center justify-center"
                                  title="Thread options"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <MoreVertical className="w-5 h-5 text-gray-800 dark:text-neutral-300" />
                                </button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-36">
                                <DropdownMenuItem
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleEditTitle(thread.thread_id, thread.title || '', e);
                                  }}
                                  className="cursor-pointer"
                                >
                                  <Edit className="w-4 h-4 mr-2" />
                                  Rename
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  variant="destructive"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteThread(thread.thread_id, thread.title || '', e);
                                  }}
                                  className="cursor-pointer"
                                >
                                  <Trash2 className="w-4 h-4 mr-2" />
                                  Delete
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        )}
                      </div>
                    </div>
                      ))}
                    </>
                  )}

                  {/* Yesterday Section */}
                  {groupedThreads.yesterday.length > 0 && (
                    <>
                      <div className="px-3 py-2">
                        <div className="text-xs font-semibold text-gray-500 dark:text-neutral-400 uppercase tracking-wider">Yesterday</div>
                      </div>
                      {groupedThreads.yesterday.map((thread) => (
                    <div
                      key={thread.thread_id}
                      className={`relative group rounded-lg transition-colors min-w-0 ${
                        selectedThreadId === thread.thread_id 
                          ? 'bg-gray-100 dark:bg-neutral-700' 
                          : 'hover:bg-gray-50 dark:hover:bg-neutral-600'
                      }`}
                    >
                      <div
                        onClick={() => handleThreadSelect(thread.thread_id)}
                        className="flex items-start gap-2 p-3 cursor-pointer min-w-0 relative"
                      >
                        <div className="min-w-0 flex-1 overflow-hidden group-hover:pr-10">
                          {editingTitle === thread.thread_id ? (
                            <div className="flex items-center gap-2 min-w-0" onClick={(e) => e.stopPropagation()}>
                              <Input
                                type="text"
                                value={newTitle}
                                onChange={(e) => setNewTitle(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    handleSaveTitle(thread.thread_id);
                                  } else if (e.key === 'Escape') {
                                    handleCancelEdit();
                                  }
                                }}
                                onBlur={() => handleSaveTitle(thread.thread_id)}
                                className="flex-1 h-7 text-sm bg-white border-gray-300 text-gray-900 dark:bg-neutral-700 dark:text-white min-w-0 max-w-full"
                                autoFocus
                              />
                            </div>
                          ) : (
                            <>
                              <div className="font-medium text-sm text-gray-900 dark:text-white min-w-0 flex items-center">
                                <MessageSquare className="w-3 h-3 mr-2 flex-shrink-0" />
                                <span className="flex-1 truncate min-w-0">{thread.title || 'Untitled Chat'}</span>
                              </div>
                              {thread.last_message && (
                                <div className="text-xs text-gray-500 dark:text-neutral-400 truncate whitespace-nowrap mt-0.5 min-w-0 flex-1">
                                  {thread.last_message}
                                </div>
                              )}
                            </>
                          )}
                        </div>

                        {/* Actions Button using shadcn DropdownMenu - only show on hover */}
                        {editingTitle !== thread.thread_id && (
                          <div className="absolute right-3 top-3 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <button
                                  className="p-1.5 hover:bg-gray-200 dark:hover:bg-neutral-700 rounded transition-all flex-shrink-0 w-8 h-8 flex items-center justify-center"
                                  title="Thread options"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <MoreVertical className="w-5 h-5 text-gray-800 dark:text-neutral-300" />
                                </button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-36">
                                <DropdownMenuItem
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleEditTitle(thread.thread_id, thread.title || '', e);
                                  }}
                                  className="cursor-pointer"
                                >
                                  <Edit className="w-4 h-4 mr-2" />
                                  Rename
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  variant="destructive"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteThread(thread.thread_id, thread.title || '', e);
                                  }}
                                  className="cursor-pointer"
                                >
                                  <Trash2 className="w-4 h-4 mr-2" />
                                  Delete
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        )}
                      </div>
                    </div>
                      ))}
                    </>
                  )}

                  {/* Older Section */}
                  {groupedThreads.older.length > 0 && (
                    <>
                      <div className="px-3 py-2">
                        <div className="text-xs font-semibold text-gray-500 dark:text-neutral-400 uppercase tracking-wider">Older</div>
                      </div>
                      {groupedThreads.older.map((thread) => (
                    <div
                      key={thread.thread_id}
                      className={`relative group rounded-lg transition-colors min-w-0 ${
                        selectedThreadId === thread.thread_id 
                          ? 'bg-gray-100 dark:bg-neutral-700' 
                          : 'hover:bg-gray-50 dark:hover:bg-neutral-600'
                      }`}
                    >
                      <div
                        onClick={() => handleThreadSelect(thread.thread_id)}
                        className="flex items-start gap-2 p-3 cursor-pointer min-w-0 relative"
                      >
                        <div className="min-w-0 flex-1 overflow-hidden group-hover:pr-10">
                          {editingTitle === thread.thread_id ? (
                            <div className="flex items-center gap-2 min-w-0" onClick={(e) => e.stopPropagation()}>
                              <Input
                                type="text"
                                value={newTitle}
                                onChange={(e) => setNewTitle(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    handleSaveTitle(thread.thread_id);
                                  } else if (e.key === 'Escape') {
                                    handleCancelEdit();
                                  }
                                }}
                                onBlur={() => handleSaveTitle(thread.thread_id)}
                                className="flex-1 h-7 text-sm bg-white border-gray-300 text-gray-900 dark:bg-neutral-700 dark:text-white min-w-0 max-w-full"
                                autoFocus
                              />
                            </div>
                          ) : (
                            <>
                              <div className="font-medium text-sm text-gray-900 dark:text-white min-w-0 flex items-center">
                                <MessageSquare className="w-3 h-3 mr-2 flex-shrink-0" />
                                <span className="flex-1 truncate min-w-0">{thread.title || 'Untitled Chat'}</span>
                              </div>
                              {thread.last_message && (
                                <div className="text-xs text-gray-500 dark:text-neutral-400 truncate whitespace-nowrap mt-0.5 min-w-0 flex-1">
                                  {thread.last_message}
                                </div>
                              )}
                            </>
                          )}
                        </div>

                        {/* Actions Button using shadcn DropdownMenu - only show on hover */}
                        {editingTitle !== thread.thread_id && (
                          <div className="absolute right-3 top-3 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <button
                                  className="p-1.5 hover:bg-gray-200 dark:hover:bg-neutral-700 rounded transition-all flex-shrink-0 w-8 h-8 flex items-center justify-center"
                                  title="Thread options"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <MoreVertical className="w-5 h-5 text-gray-800 dark:text-neutral-300" />
                                </button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-36">
                                <DropdownMenuItem
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleEditTitle(thread.thread_id, thread.title || '', e);
                                  }}
                                  className="cursor-pointer"
                                >
                                  <Edit className="w-4 h-4 mr-2" />
                                  Rename
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  variant="destructive"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteThread(thread.thread_id, thread.title || '', e);
                                  }}
                                  className="cursor-pointer"
                                >
                                  <Trash2 className="w-4 h-4 mr-2" />
                                  Delete
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        )}
                      </div>
                    </div>
                      ))}
                    </>
                  )}
                </div>
              )
            ) : null}
          </ScrollArea>
        </div>

        {/* Footer */}
          <div className="p-2 border-t border-gray-200 dark:border-neutral-700 overflow-hidden space-y-1 pb-[env(safe-area-inset-bottom)]">
          {isExpanded && (
            <Button
              onClick={loadThreads}
              variant="ghost"
              className="w-full h-10 text-xs text-gray-600 dark:text-neutral-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-neutral-700 justify-start pl-3"
            >
              Refresh Threads
            </Button>
          )}

          {/* Settings dropdown */}
          <div className="relative">
            <button
              onClick={() => {
                if (isExpanded) {
                  setSettingsOpen(prev => !prev);
                }
              }}
              className="w-full h-10 flex items-center pl-3 hover:bg-gray-100 dark:hover:bg-neutral-700 rounded-md transition-colors"
              title={!isExpanded ? "Settings" : undefined}
            >
              <Settings className="w-4 h-4 flex-shrink-0" />
              {isExpanded && (
                <>
                  <span className="ml-2 text-xs font-medium whitespace-nowrap overflow-hidden">
                    Settings
                  </span>
                  <ChevronDown className={`w-4 h-4 mr-2 ml-auto transition-transform ${settingsOpen ? 'rotate-180' : ''}`} />
                </>
              )}
            </button>
            {isExpanded && settingsOpen && (
              <div className="mt-1 border border-gray-200 dark:border-neutral-700 rounded-md shadow-sm bg-white dark:bg-neutral-900">
                {/* Dark Mode Toggle */}
                <div className="flex items-center justify-between px-3 py-2">
                  <span className="text-sm text-gray-700 dark:text-white">Dark Mode</span>
                  <DarkModeToggle size="sm" />
                </div>
                <div className="border-t border-gray-200 dark:border-neutral-700 my-1" />
                <button
                  onClick={async () => { await signOut(); }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded"
                >
                  <LogOut className="w-4 h-4" />
                  Sign out{user?.email ? ` (${user.email})` : ''}
                </button>
              </div>
            )}
          </div>
        </div>
        </div>
      </aside>

      {/* Delete Thread Dialog */}
      <DeleteThreadDialog
        isOpen={deleteDialog.isOpen}
        threadTitle={deleteDialog.threadTitle}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
      />
    </>
  );
};

export default EnhancedSidebar2;