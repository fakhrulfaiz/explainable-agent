import React, { useState, useEffect } from 'react';
import { ChevronDown, Plus, MessageSquare, Calendar, MoreVertical, Trash2, Edit } from 'lucide-react';
import { ChatHistoryService, ChatThreadSummary } from '../api/services/chatHistoryService';

interface ChatThreadSelectorProps {
  selectedThreadId?: string;
  onThreadSelect: (threadId: string | null) => void;
  onNewThread: () => void;
  className?: string;
}

const ChatThreadSelector: React.FC<ChatThreadSelectorProps> = ({
  selectedThreadId,
  onThreadSelect,
  onNewThread,
  className = ""
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [threads, setThreads] = useState<ChatThreadSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showActions, setShowActions] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);

 
  const selectedThread = threads.find(t => t.thread_id === selectedThreadId);

  // Load threads when component mounts or dropdown opens
  useEffect(() => {
    if (isOpen && threads.length === 0) {
      loadThreads();
    }
  }, [isOpen]);

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
    setIsOpen(false);
    setShowActions(null);
    setMenuPosition(null);
  };

  const handleNewThread = () => {
    onNewThread();
    setIsOpen(false);
    setShowActions(null);
    setMenuPosition(null);
  };

  const handleDeleteThread = async (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (!confirm('Are you sure you want to delete this chat thread?')) {
      return;
    }

    try {
      await ChatHistoryService.deleteThread(threadId);
      setThreads(prev => prev.filter(t => t.thread_id !== threadId));
      
      // If the deleted thread was selected, clear selection
      if (selectedThreadId === threadId) {
        onThreadSelect(null);
      }
      
      setShowActions(null);
      setMenuPosition(null);
    } catch (err) {
      console.error('Error deleting thread:', err);
      alert('Failed to delete thread');
    }
  };

  const handleEditTitle = (threadId: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingTitle(threadId);
    setNewTitle(currentTitle || 'Untitled Chat');
    setShowActions(null);
    setMenuPosition(null);
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
    setMenuPosition(null);
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

  return (
    <div className={`relative ${className}`}>
      {/* Selected Thread Display / Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <MessageSquare className="w-4 h-4 text-gray-500 flex-shrink-0" />
          <span className="truncate text-left">
            {selectedThread ? (
              selectedThread.title || 'Untitled Chat'
            ) : (
              'Select a chat thread'
            )}
          </span>
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300 rounded-lg shadow-lg z-50 max-h-96 overflow-hidden">
          {/* New Thread Button */}
          <button
            onClick={handleNewThread}
            className="w-full flex items-center gap-2 p-3 hover:bg-gray-50 border-b border-gray-200 text-blue-600"
          >
            <Plus className="w-4 h-4" />
            <span>New Chat Thread</span>
          </button>

          {/* Threads List */}
          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-center text-gray-500">
                Loading threads...
              </div>
            ) : error ? (
              <div className="p-4 text-center text-red-500">
                {error}
                <button 
                  onClick={loadThreads}
                  className="block mx-auto mt-2 text-blue-600 hover:underline"
                >
                  Retry
                </button>
              </div>
            ) : threads.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                No chat threads found
              </div>
            ) : (
              threads.map((thread) => (
                <div
                  key={thread.thread_id}
                  className={`relative group border-b border-gray-100 last:border-b-0 ${
                    selectedThreadId === thread.thread_id ? 'bg-blue-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <div
                    onClick={() => handleThreadSelect(thread.thread_id)}
                    className="flex items-center justify-between p-3 cursor-pointer"
                  >
                    <div className="min-w-0 flex-1">
                      {editingTitle === thread.thread_id ? (
                        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="text"
                            value={newTitle}
                            onChange={(e) => setNewTitle(e.target.value)}
                            onKeyPress={(e) => {
                              if (e.key === 'Enter') {
                                handleSaveTitle(thread.thread_id);
                              } else if (e.key === 'Escape') {
                                handleCancelEdit();
                              }
                            }}
                            onBlur={() => handleSaveTitle(thread.thread_id)}
                            className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                            autoFocus
                          />
                        </div>
                      ) : (
                        <>
                          <div className="font-medium text-sm truncate">
                            {thread.title || 'Untitled Chat'}
                          </div>
                          {thread.last_message && (
                            <div className="text-xs text-gray-500 truncate mt-1">
                              {thread.last_message}
                            </div>
                          )}
                          <div className="flex items-center gap-4 mt-1 text-xs text-gray-400">
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {formatDate(thread.updated_at)}
                            </span>
                            <span>{thread.message_count} messages</span>
                          </div>
                        </>
                      )}
                    </div>

                    {/* Actions Button */}
                    {editingTitle !== thread.thread_id && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          const rect = e.currentTarget.getBoundingClientRect();
                          setMenuPosition({
                            top: rect.bottom + 4,
                            left: rect.right - 120 // Position menu to the right of the button
                          });
                          setShowActions(showActions === thread.thread_id ? null : thread.thread_id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-200 rounded transition-all"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>
                    )}

                    {/* Actions Menu */}
                    {showActions === thread.thread_id && menuPosition && (
                      <div 
                        className="fixed bg-white border border-gray-300 rounded-lg shadow-lg z-50 min-w-32"
                        style={{
                          top: `${menuPosition.top}px`,
                          left: `${menuPosition.left}px`
                        }}
                      >
                        <button
                          onClick={(e) => handleEditTitle(thread.thread_id, thread.title || '', e)}
                          className="w-full flex items-center gap-2 p-2 hover:bg-gray-50 text-left text-sm"
                        >
                          <Edit className="w-3 h-3" />
                          Edit Title
                        </button>
                        <button
                          onClick={(e) => handleDeleteThread(thread.thread_id, e)}
                          className="w-full flex items-center gap-2 p-2 hover:bg-gray-50 text-left text-sm text-red-600"
                        >
                          <Trash2 className="w-3 h-3" />
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Refresh Button */}
          <div className="border-t border-gray-200 p-2">
            <button
              onClick={loadThreads}
              className="w-full text-xs text-gray-500 hover:text-gray-700 py-1"
            >
              Refresh Threads
            </button>
          </div>
        </div>
      )}

      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => {
            setIsOpen(false);
            setShowActions(null);
            setEditingTitle(null);
            setMenuPosition(null);
          }}
        />
      )}
    </div>
  );
};

export default ChatThreadSelector;
