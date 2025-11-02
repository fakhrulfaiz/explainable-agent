import React, { useState, useEffect, useRef } from 'react';
import { Plus, Search, MessageSquare, Calendar, MoreVertical, Trash2, Edit, PanelLeftClose, PanelLeftOpen, Settings, ChevronDown, LogOut } from 'lucide-react';
import { ChatHistoryService, ChatThreadSummary } from '../api/services/chatHistoryService';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';
import { Button } from './ui/button';
import { Input } from './ui/input';
import DeleteThreadDialog from './DeleteThreadDialog';
import DarkModeToggle from './DarkModeToggle';
import { useAuth } from '@/contexts/AuthContext';

interface SidebarProps {
  selectedThreadId?: string;
  onThreadSelect: (threadId: string | null) => void;
  onNewThread: () => void;
  isOpen: boolean;
  onToggle: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({
  selectedThreadId,
  onThreadSelect,
  onNewThread,
  isOpen,
  onToggle
}) => {
  const [threads, setThreads] = useState<ChatThreadSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showActions, setShowActions] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteDialog, setDeleteDialog] = useState<{ isOpen: boolean; threadId: string; threadTitle: string }>({
    isOpen: false,
    threadId: '',
    threadTitle: ''
  });
  const [actionMenuPosition, setActionMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const actionButtonRef = useRef<HTMLButtonElement>(null);
  const { user, signOut } = useAuth();
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Load threads only on first open (or via Refresh)
  useEffect(() => {
    if (isOpen && threads.length === 0) {
      loadThreads();
    }
  }, [isOpen, threads.length]);

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

  const handleThreadSelect = (threadId: string) => {
    onThreadSelect(threadId);
    setShowActions(null);
    setActionMenuPosition(null);
  };

  const handleNewThread = () => {
    onNewThread();
    setShowActions(null);
    setActionMenuPosition(null);
  };

  const handleDeleteThread = (threadId: string, threadTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteDialog({
      isOpen: true,
      threadId,
      threadTitle: threadTitle || 'Untitled Chat'
    });
    setShowActions(null);
    setActionMenuPosition(null);
  };

  const handleConfirmDelete = async () => {
    try {
      await ChatHistoryService.deleteThread(deleteDialog.threadId);
      setThreads(prev => prev.filter(t => t.thread_id !== deleteDialog.threadId));
      
      if (selectedThreadId === deleteDialog.threadId) {
        onThreadSelect(null);
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

  const handleEditTitle = (threadId: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingTitle(threadId);
    setNewTitle(currentTitle || 'Untitled Chat');
    setShowActions(null);
    setActionMenuPosition(null);
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

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return 'Today';
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  // Filter threads based on search query (placeholder for future)
  const filteredThreads = threads.filter(thread => 
    thread.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    thread.last_message?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      {/* Collapsed Sidebar - original style on desktop, mobile button only */}
      {!isOpen && (
        <>
          {/* Desktop: Original collapsed sidebar */}
          <aside className="hidden md:flex fixed top-0 left-0 h-[100vh] bg-white dark:bg-neutral-800 border-r border-gray-200 dark:border-neutral-700 w-16 z-40 flex-col items-center py-4 gap-2">
            {/* Toggle Button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggle}
              className="hover:bg-gray-100 dark:hover:bg-neutral-700 w-12 h-12 focus:outline-none focus-visible:ring-0"
              title="Expand sidebar"
            >
              <PanelLeftOpen className="h-5 w-5" />
              </Button>
            <Separator className="bg-gray-200 dark:bg-neutral-700 w-12" />

            {/* New Chat Button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={handleNewThread}
              className="hover:bg-gray-100 dark:hover:bg-neutral-700 w-12 h-12 focus:outline-none focus-visible:ring-0"
              title="New Thread"
            >
              <Plus className="h-5 w-5" />
            </Button>
          </aside>

          {/* Mobile/Tablet: Just a button to open sidebar */}
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            className="md:hidden fixed top-4 left-4 z-40 hover:bg-gray-100 dark:hover:bg-neutral-700 w-10 h-10 focus:outline-none focus-visible:ring-0 bg-white dark:bg-neutral-800 border border-gray-200 dark:border-neutral-700 shadow-sm"
            title="Open sidebar"
          >
            <PanelLeftOpen className="h-4 w-4" />
          </Button>
        </>
      )}

      {/* Overlay for when expanded sidebar is open */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40"
          onClick={onToggle}
        />
      )}

      {/* Expanded Sidebar */}
      <aside
        className={`fixed top-0 left-0 h-[100vh] bg-white dark:bg-neutral-900 border-r border-gray-200 dark:border-neutral-700 transition-all duration-300 ease-in-out z-50 ${
          isOpen ? 'w-96 opacity-100' : 'w-0 opacity-0'
        } overflow-hidden`}
      >
        <div className="flex flex-col h-full w-96 max-w-96 overflow-hidden">
          {/* Header with Toggle and New Thread */}
          <div className="pt-4 px-3 pb-2 space-y-2">
            {/* Toggle Row - whole row clickable */}
            <Button
              variant="ghost"
              onClick={onToggle}
              className="w-full h-10 flex items-center gap-3 justify-start hover:bg-gray-100 dark:hover:bg-neutral-800 focus:outline-none focus-visible:ring-0"
              title="Collapse sidebar"
            >
              <PanelLeftClose className="h-5 w-5" />
              <span className="font-semibold text-lg text-gray-900 dark:text-white">Explainable Agent</span>
            </Button>

            {/* New Thread Row - whole row clickable */}
            <Button
              variant="ghost"
              onClick={() => { handleNewThread(); onToggle(); }}
              className="w-full h-10 flex items-center gap-3 justify-start hover:bg-gray-100 dark:hover:bg-neutral-800 focus:outline-none focus-visible:ring-0"
              title="New Thread"
            >
              <Plus className="h-5 w-5" />
              <span className="font-medium text-gray-700 dark:text-white">New Threads</span>
            </Button>
          </div>

          <Separator className="bg-gray-200 dark:bg-neutral-700" />

          {/* Search Bar */}
          <div className="p-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-neutral-400" />
              <Input
                type="text"
                placeholder="Search chats..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 bg-white dark:bg-neutral-800 border-gray-300 dark:border-neutral-600 text-gray-900 dark:text-neutral-200 placeholder-gray-400 dark:placeholder-[#c1c5ce] focus:border-gray-400 dark:focus:border-neutral-500 focus-visible:ring-0"
              />
            </div>
          </div>

          <Separator className="bg-gray-200" />

          {/* Threads List */}
          <div className="flex-1 overflow-hidden">
            <ScrollArea className="h-full px-2">
            {loading ? (
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
              <div className="space-y-1 py-2 max-w-full overflow-hidden">
                {filteredThreads.map((thread) => (
                  <div
                    key={thread.thread_id}
                    className={`relative group rounded-lg transition-colors ${
                      selectedThreadId === thread.thread_id 
                        ? 'bg-gray-100 dark:bg-neutral-800' 
                        : 'hover:bg-gray-50 dark:hover:bg-neutral-800'
                    }`}
                  >
                    <div
                      onClick={() => { handleThreadSelect(thread.thread_id); onToggle(); }}
                      className="flex items-start gap-2 p-3 cursor-pointer min-w-0 w-full"
                    >
                      <div className="min-w-0 flex-1 overflow-hidden max-w-[calc(100%-3rem)]">
                        {editingTitle === thread.thread_id ? (
                          <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
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
                              className="flex-1 h-7 text-sm bg-white border-gray-300 text-gray-900"
                              autoFocus
                            />
                          </div>
                        ) : (
                          <>
                            <div className="font-medium text-sm truncate mb-1 text-gray-900 dark:text-white max-w-[250px]">
                              <MessageSquare className="w-3 h-3 inline mr-2" />
                              {thread.title || 'Untitled Chat'}
                            </div>
                            {thread.last_message && (
                              <div className="text-xs text-gray-500 dark:text-neutral-400 truncate max-w-[250px]">
                                {thread.last_message}
                              </div>
                            )}
                            <div className="flex items-center gap-2 mt-1 text-xs text-gray-400 dark:text-neutral-500">
                              <span className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" />
                                {formatDate(thread.updated_at)}
                              </span>
                            </div>
                          </>
                        )}
                      </div>

                       {/* Actions Button */}
                       {editingTitle !== thread.thread_id && (
                         <button
                           ref={actionButtonRef}
                           onClick={(e) => {
                             e.stopPropagation();
                             if (showActions === thread.thread_id) {
                               setShowActions(null);
                               setActionMenuPosition(null);
                             } else {
                               const rect = e.currentTarget.getBoundingClientRect();
                               setActionMenuPosition({
                                 top: rect.bottom + 4,
                                 left: rect.right - 144 // 144px is min-w-36 (9rem)
                               });
                               setShowActions(thread.thread_id);
                             }
                           }}
                           className="opacity-100 p-1.5 hover:bg-gray-200 dark:hover:bg-neutral-700 rounded transition-all flex-shrink-0 w-8 h-8 flex items-center justify-center ml-2"
                           title="Thread options"
                         >
                           <MoreVertical className="w-5 h-5 text-gray-800 dark:text-neutral-300" />
                         </button>
                       )}
                    </div>

                     {/* Actions Menu */}
                     {showActions === thread.thread_id && actionMenuPosition && (
                         <div 
                         className="fixed bg-white dark:bg-neutral-900 border border-gray-200 dark:border-neutral-700 rounded-lg shadow-lg z-[200] min-w-36"
                         style={{
                           top: `${actionMenuPosition.top}px`,
                           left: `${actionMenuPosition.left}px`
                         }}
                       >
                        <button
                          onClick={(e) => handleEditTitle(thread.thread_id, thread.title || '', e)}
                          className="w-full flex items-center gap-2 p-2 hover:bg-gray-50 dark:hover:bg-neutral-800 text-left text-sm text-gray-700 dark:text-neutral-200"
                        >
                          <Edit className="w-3 h-3" />
                          Rename
                        </button>
                        <button
                          onClick={(e) => handleDeleteThread(thread.thread_id, thread.title || '', e)}
                          className="w-full flex items-center gap-2 p-2 hover:bg-gray-50 dark:hover:bg-neutral-800 text-left text-sm text-red-600"
                        >
                          <Trash2 className="w-3 h-3" />
                          Delete
                        </button>
                      </div>
                     )}
                  </div>
                ))}
              </div>
            )}
            </ScrollArea>
          </div>

          {/* Footer with Settings */}
          <div className="p-3 border-t border-gray-200 dark:border-gray-700">
            <div className="space-y-2">
              <Button
                onClick={loadThreads}
                variant="ghost"
                className="w-full text-xs text-gray-600 dark:text-neutral-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-neutral-700"
              >
                Refresh Threads
              </Button>

              {/* Settings dropdown */}
              <div className="relative">
                <button
                  onClick={() => setSettingsOpen(prev => !prev)}
                  className="w-full flex items-center justify-between gap-3 px-3 py-2 rounded hover:bg-gray-100 dark:hover:bg-neutral-700 text-gray-700 dark:text-neutral-300"
                  title="Settings"
                >
                  <span className="flex items-center gap-2">
                    <Settings className="w-4 h-4" />
                    <span className="text-sm font-medium">Settings</span>
                  </span>
                  <ChevronDown className={`w-4 h-4 transition-transform ${settingsOpen ? 'rotate-180' : ''}`} />
                </button>
                {settingsOpen && (
                  <div className="mt-1 border border-gray-200 dark:border-neutral-700 rounded-md shadow-sm bg-white dark:bg-neutral-900">
                    {/* Dark Mode Toggle */}
                    <div className="flex items-center justify-between px-3 py-2">
                      <span className="text-sm text-gray-700 dark:text-white">Dark Mode</span>
                      <DarkModeToggle size="sm" />
                    </div>
                    <Separator className="my-1" />
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
        </div>
      </aside>

      {/* Click outside to close actions menu */}
      {showActions && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowActions(null)}
        />
      )}

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

export default Sidebar;

