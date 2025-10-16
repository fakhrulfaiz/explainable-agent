import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, ChevronUp, Edit3, Check, X } from 'lucide-react';
import { ChatHistoryService } from '../api/services/chatHistoryService';

interface ThreadTitleProps {
  title: string;
  threadId?: string;
  onTitleChange?: (newTitle: string) => void;
  className?: string;
}

const ThreadTitle: React.FC<ThreadTitleProps> = ({ 
  title, 
  threadId,
  onTitleChange, 
  className = "" 
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(title);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setIsEditing(false);
        setEditValue(title);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [title]);

  // Focus input when editing starts
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  // Update edit value when title prop changes
  useEffect(() => {
    setEditValue(title);
  }, [title]);

  const handleToggleDropdown = () => {
    setIsOpen(!isOpen);
  };

  const handleStartEdit = () => {
    setIsEditing(true);
    setEditValue(title);
  };

  const handleSaveEdit = async () => {
    if (!editValue.trim() || editValue === title) return;

    try {
      // If we have a threadId, update via API like in Sidebar
      if (threadId) {
        await ChatHistoryService.updateThreadTitle(threadId, editValue.trim());
      }
      
      // Always call the parent callback to update local state
      if (onTitleChange) {
        onTitleChange(editValue.trim());
      }
      
      setIsEditing(false);
      setIsOpen(false);
    } catch (err) {
      console.error('Error updating title:', err);
      alert('Failed to update title');
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditValue(title);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Thread Title Button */}
      <button
        onClick={handleToggleDropdown}
        className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-neutral-700 rounded-lg transition-colors max-w-xs"
      >
        <span className="truncate flex-1 text-left">
          {title || 'New Thread'}
        </span>
        {isOpen ? (
          <ChevronUp className="w-4 h-4 flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 flex-shrink-0" />
        )}
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-white dark:bg-neutral-800 border border-gray-200 dark:border-neutral-600 rounded-lg shadow-lg z-50">
          <div className="p-3">
            {isEditing ? (
              /* Edit Mode */
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                    Thread Title
                  </label>
                  <input
                    ref={inputRef}
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-neutral-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 bg-white dark:bg-neutral-700 text-gray-900 dark:text-gray-100"
                    placeholder="Enter thread title..."
                  />
                </div>
                <div className="flex items-center gap-2 justify-end">
                  <button
                    onClick={handleCancelEdit}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
                  >
                    <X className="w-3 h-3" />
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveEdit}
                    disabled={!editValue.trim() || editValue === title}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-800 dark:bg-white text-white dark:text-neutral-700 rounded-lg hover:bg-gray-700 dark:hover:bg-neutral-400 disabled:bg-gray-300 dark:disabled:bg-neutral-400 disabled:cursor-not-allowed transition-colors"
                  >
                    <Check className="w-3 h-3" />
                    Save
                  </button>
                </div>
              </div>
            ) : (
              /* View Mode */
              <div className="space-y-2">
                <div className="text-sm text-gray-900 dark:text-gray-100 font-medium">
                  {title || 'New Thread'}
                </div>
                <button
                  onClick={handleStartEdit}
                  className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-neutral-700 rounded transition-colors"
                >
                  <Edit3 className="w-3 h-3" />
                  Edit title
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ThreadTitle;
