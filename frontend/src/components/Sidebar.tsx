import React, { useState, useEffect } from 'react';
import { Plus, Search, MessageSquare, Calendar, MoreVertical, Trash2, Edit, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { ChatHistoryService, ChatThreadSummary } from '../api/services/chatHistoryService';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';
import { Button } from './ui/button';
import { Input } from './ui/input';
import DeleteThreadModal from './DeleteThreadModal';

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
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; threadId: string; threadTitle: string }>({
    isOpen: false,
    threadId: '',
    threadTitle: ''
  });

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
  };

  const handleNewThread = () => {
    onNewThread();
    setShowActions(null);
  };

  const handleDeleteThread = (threadId: string, threadTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteModal({
      isOpen: true,
      threadId,
      threadTitle: threadTitle || 'Untitled Chat'
    });
    setShowActions(null);
  };

  const handleConfirmDelete = async () => {
    try {
      await ChatHistoryService.deleteThread(deleteModal.threadId);
      setThreads(prev => prev.filter(t => t.thread_id !== deleteModal.threadId));
      
      if (selectedThreadId === deleteModal.threadId) {
        onThreadSelect(null);
      }
      
      setDeleteModal({ isOpen: false, threadId: '', threadTitle: '' });
    } catch (err) {
      console.error('Error deleting thread:', err);
      alert('Failed to delete thread');
    }
  };

  const handleCancelDelete = () => {
    setDeleteModal({ isOpen: false, threadId: '', threadTitle: '' });
  };

  const handleEditTitle = (threadId: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingTitle(threadId);
    setNewTitle(currentTitle || 'Untitled Chat');
    setShowActions(null);
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
      {/* Collapsed Sidebar - shown only when not expanded */}
      {!isOpen && (
        <aside className="fixed top-16 left-0 h-[calc(100vh-4rem)] bg-white border-r border-gray-200 w-16 z-40 flex flex-col items-center py-4 gap-2">
          {/* Toggle Button */}
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            className="hover:bg-gray-100 w-12 h-12 focus:outline-none focus-visible:ring-0"
            title="Expand sidebar"
          >
            <PanelLeftOpen className="h-5 w-5" />
          </Button>

          <Separator className="bg-gray-200 w-12" />

          {/* New Chat Button */}
          <Button
            variant="ghost"
            size="icon"
            onClick={handleNewThread}
            className="hover:bg-gray-100 w-12 h-12 focus:outline-none focus-visible:ring-0"
            title="New Thread"
          >
            <Plus className="h-5 w-5" />
          </Button>
        </aside>
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
        className={`fixed top-16 left-0 h-[calc(100vh-4rem)] bg-white border-r border-gray-200 transition-all duration-300 ease-in-out z-50 ${
          isOpen ? 'w-96 opacity-100' : 'w-0 opacity-0'
        } overflow-hidden`}
      >
        <div className="flex flex-col h-full w-96">
          {/* Header with Toggle and New Thread */}
          <div className="pt-4 px-3 pb-2 space-y-2">
            {/* Toggle Row - whole row clickable */}
            <Button
              variant="ghost"
              onClick={onToggle}
              className="w-full h-10 flex items-center gap-3 justify-start hover:bg-gray-100 focus:outline-none focus-visible:ring-0"
              title="Collapse sidebar"
            >
              <PanelLeftClose className="h-5 w-5" />
              <span className="font-semibold text-lg text-gray-900">Explainable Agent</span>
            </Button>

            {/* New Thread Row - whole row clickable */}
            <Button
              variant="ghost"
              onClick={() => { handleNewThread(); onToggle(); }}
              className="w-full h-10 flex items-center gap-3 justify-start hover:bg-gray-100 focus:outline-none focus-visible:ring-0"
              title="New Thread"
            >
              <Plus className="h-5 w-5" />
              <span className="font-medium text-gray-700">New Threads</span>
            </Button>
          </div>

          <Separator className="bg-gray-200" />

          {/* Search Bar */}
          <div className="p-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                type="text"
                placeholder="Search chats..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 bg-white border-gray-300 text-gray-900 placeholder-gray-400 focus:border-gray-400 focus-visible:ring-0"
              />
            </div>
          </div>

          <Separator className="bg-gray-200" />

          {/* Threads List */}
          <ScrollArea className="flex-1 px-2">
            {loading ? (
              <div className="p-4 text-center text-gray-500 text-sm">
                Loading threads...
              </div>
            ) : error ? (
              <div className="p-4 text-center text-red-500 text-sm">
                {error}
                <Button 
                  onClick={loadThreads}
                  variant="link"
                  className="block mx-auto mt-2 text-blue-600 hover:text-blue-700"
                >
                  Retry
                </Button>
              </div>
            ) : filteredThreads.length === 0 ? (
              <div className="p-4 text-center text-gray-500 text-sm">
                {searchQuery ? 'No matching threads' : 'No chat threads found'}
              </div>
            ) : (
              <div className="space-y-1 py-2">
                {filteredThreads.map((thread) => (
                  <div
                    key={thread.thread_id}
                    className={`relative group rounded-lg transition-colors ${
                      selectedThreadId === thread.thread_id 
                        ? 'bg-gray-100' 
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <div
                      onClick={() => { handleThreadSelect(thread.thread_id); onToggle(); }}
                      className="flex items-start justify-between p-3 cursor-pointer"
                    >
                      <div className="min-w-0 flex-1 pr-3">
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
                            <div className="font-medium text-sm truncate mb-1 text-gray-900">
                              <MessageSquare className="w-3 h-3 inline mr-2" />
                              {thread.title || 'Untitled Chat'}
                            </div>
                            {thread.last_message && (
                              <div className="text-xs text-gray-500 truncate max-w-[200px]">
                                {thread.last_message}
                              </div>
                            )}
                            <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
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
                          onClick={(e) => {
                            e.stopPropagation();
                            setShowActions(showActions === thread.thread_id ? null : thread.thread_id);
                          }}
                          className="opacity-30 group-hover:opacity-100 p-1.5 hover:bg-gray-200 rounded transition-all flex-shrink-0 w-8 h-8 flex items-center justify-center"
                          title="Thread options"
                        >
                          <MoreVertical className="w-4 h-4 text-gray-600" />
                        </button>
                      )}
                    </div>

                    {/* Actions Menu */}
                    {showActions === thread.thread_id && (
                      <div className="absolute right-3 top-12 bg-white border border-gray-200 rounded-lg shadow-lg z-50 min-w-36">
                        <button
                          onClick={(e) => handleEditTitle(thread.thread_id, thread.title || '', e)}
                          className="w-full flex items-center gap-2 p-2 hover:bg-gray-50 text-left text-sm text-gray-700"
                        >
                          <Edit className="w-3 h-3" />
                          Rename
                        </button>
                        <button
                          onClick={(e) => handleDeleteThread(thread.thread_id, thread.title || '', e)}
                          className="w-full flex items-center gap-2 p-2 hover:bg-gray-50 text-left text-sm text-red-600"
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

          {/* Footer */}
          <div className="p-3 border-t border-gray-200">
            <Button
              onClick={loadThreads}
              variant="ghost"
              className="w-full text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            >
              Refresh Threads
            </Button>
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

      {/* Delete Thread Modal */}
      <DeleteThreadModal
        isOpen={deleteModal.isOpen}
        threadTitle={deleteModal.threadTitle}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
      />
    </>
  );
};

export default Sidebar;

