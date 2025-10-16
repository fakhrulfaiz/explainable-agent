
import React, { useState, useRef } from 'react';
import { Send, Plus, X, Upload, File, Image, FileText, FileCode, Zap, Brain, ChevronDown } from 'lucide-react';
import { useUIState } from '../contexts/UIStateContext';
import LLMSelector from './LLMSelector';
interface EnhancedInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  placeholder?: string;
  disabled?: boolean;
  isLoading?: boolean;
  usePlanning?: boolean;
  useExplainer?: boolean;
  onPlanningToggle?: (enabled: boolean) => void;
  onExplainerToggle?: (enabled: boolean) => void;
  onFilesChange?: (files: File[]) => void;
  attachedFiles?: File[];
}

const EnhancedInput: React.FC<EnhancedInputProps> = ({
  value,
  onChange,
  onSend,
  onKeyDown,
  placeholder = "Type your message...",
  disabled = false,
  isLoading = false,
  usePlanning = false,
  useExplainer = false,
  onPlanningToggle,
  onExplainerToggle,
  onFilesChange,
  attachedFiles = []
}) => {
  const [showInputOptions, setShowInputOptions] = useState<boolean>(false);
  const [isTextareaExpanded, setIsTextareaExpanded] = useState<boolean>(false);
  const { state, setUseStreaming } = useUIState();
  const useStreaming = state.useStreaming;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const files = Array.from(e.target.files || []);
    if (onFilesChange) {
      onFilesChange([...attachedFiles, ...files]);
    }
  };

  const removeFile = (index: number): void => {
    if (onFilesChange) {
      onFilesChange(attachedFiles.filter((_, i) => i !== index));
    }
  };

  const togglePlanning = (): void => {
    if (onPlanningToggle) {
      onPlanningToggle(!usePlanning);
    }
  };

  const toggleExplainer = (): void => {
    if (onExplainerToggle) {
      onExplainerToggle(!useExplainer);
    }
  };

  const toggleInputOptions = (): void => {
    setShowInputOptions(prev => !prev);
  };

  const getFileIcon = (file: File) => {
    const fileType = file.type;
    if (fileType.startsWith('image/')) return <Image className="w-3 h-3" />;
    if (fileType.includes('text/') || fileType.includes('document')) return <FileText className="w-3 h-3" />;
    if (fileType.includes('code') || fileType.includes('javascript') || fileType.includes('json')) return <FileCode className="w-3 h-3" />;
    return <File className="w-3 h-3" />;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleTextareaInput = (e: React.FormEvent<HTMLTextAreaElement>) => {
    const target = e.target as HTMLTextAreaElement;
    target.style.height = 'auto';
    target.style.height = `${target.scrollHeight}px`;
    
    // Check if content exceeds max height (max-h-64 = 16rem = 256px)
    const maxHeight = 256; // 16rem in pixels
    setIsTextareaExpanded(target.scrollHeight > maxHeight);
  };

  const handleTextareaKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    } else {
      onKeyDown(e);
    }
  };

  // Check expansion state when value changes
  React.useEffect(() => {
    if (textareaRef.current) {
      const maxHeight = 256; // 16rem in pixels
      setIsTextareaExpanded(textareaRef.current.scrollHeight > maxHeight);
    }
  }, [value]);

  return (
    <div className="space-y-2 border border-gray-300 dark:border-neutral-600 rounded-2xl p-4 w-full max-w-3xl mx-auto bg-gray-50 dark:bg-neutral-700">
      {/* Enhanced Input Options */}
      {showInputOptions && (
        <div className="p-2 bg-gray-50 dark:bg-neutral-600 rounded-2xl border dark:border-neutral-500 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={togglePlanning}
              className={`flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs transition-colors h-5 w-24 ${
                usePlanning 
                  ? 'bg-blue-100 dark:bg-blue-800 text-blue-700 dark:text-blue-200 border border-blue-200 dark:border-blue-600' 
                  : 'bg-gray-100 dark:bg-neutral-500 text-gray-600 dark:text-neutral-200 hover:bg-gray-200 dark:hover:bg-neutral-400'
              }`}
            >
              {usePlanning ? <X className="w-2.5 h-2.5" /> : <Plus className="w-2.5 h-2.5" />}
              {usePlanning ? 'Planning On' : 'Planning Off'}
            </button>
            
            <button
              onClick={toggleExplainer}
              className={`flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs transition-colors h-5 w-26 ${
                useExplainer 
                  ? 'bg-emerald-100 dark:bg-emerald-800 text-emerald-700 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-600' 
                  : 'bg-gray-100 dark:bg-neutral-500 text-gray-600 dark:text-neutral-200 hover:bg-gray-200 dark:hover:bg-neutral-400'
              }`}
            >
              <Brain className="w-2.5 h-2.5" />
              {useExplainer ? 'Explainer On' : 'Explainer Off'}
            </button>
            
            <button
              onClick={() => setUseStreaming(!useStreaming)}
              className={`flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs transition-colors h-5 w-26 ${
                useStreaming 
                  ? 'bg-purple-100 dark:bg-purple-800 text-purple-700 dark:text-purple-200 border border-purple-200 dark:border-purple-600' 
                  : 'bg-gray-100 dark:bg-neutral-500 text-gray-600 dark:text-neutral-200 hover:bg-gray-200 dark:hover:bg-neutral-400'
              }`}
            >
              <Zap className="w-2.5 h-2.5" />
              {useStreaming ? 'Streaming On' : 'Streaming Off'}
            </button>
            
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs h-5 w-18 bg-gray-100 dark:bg-neutral-500 text-gray-600 dark:text-neutral-200 hover:bg-gray-200 dark:hover:bg-neutral-400 transition-colors"
            >
              <Upload className="w-2.5 h-2.5" />
              Upload
            </button>
          </div>
          
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*"
            onChange={handleFileUpload}
            className="hidden"
          />
        </div>
      )}

      {/* Main Input Area */
      }
      <div className="flex gap-2 w-full">
        <div className="flex-1 relative text-base">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleTextareaKeyDown}
            onInput={handleTextareaInput}
            placeholder={placeholder}
            disabled={disabled || isLoading}
            rows={1}
            className={`w-full px-3 py-1.5 border border-gray-300 dark:border-neutral-700 rounded-2xl focus:outline-none focus:ring-0 focus:border-gray-400 dark:focus:border-neutral-700 disabled:bg-gray-100 dark:disabled:bg-neutral-500 disabled:cursor-not-allowed resize-none max-h-64 text-sm textarea-scroll min-h-[2.5rem] ${
              isTextareaExpanded ? 'overflow-y-auto' : 'overflow-y-hidden'
            }`}
          />
          
           {/* Plus button for options */}
          <button
             onClick={toggleInputOptions}
            className="absolute right-2 top-1.5 p-1.5 text-gray-400 dark:text-neutral-400 hover:text-gray-600 dark:hover:text-neutral-200 transition-colors rounded-full hover:bg-gray-100 dark:hover:bg-neutral-500"
           >
             {showInputOptions ? <ChevronDown className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
           </button>
        </div>
        
        <button
          onClick={onSend}
          disabled={!value.trim() || disabled || isLoading}
          className="px-3 py-1.5 bg-gray-800 dark:bg-white text-white dark:text-neutral-700 rounded-2xl hover:bg-gray-700 dark:hover:bg-neutral-400 disabled:bg-gray-300 dark:disabled:bg-neutral-400 disabled:cursor-not-allowed transition-colors text-sm self-start min-h-[2.5rem] flex items-center justify-center"
        >
          <Send className="w-4 h-5.5" />
        </button>
      </div>
  
      <div className="flex items-center justify-start mt-1">
        <LLMSelector compact />
      </div>

        {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {attachedFiles.map((file, index) => (
              <div key={index} className="flex items-center gap-2 px-2 py-1 bg-blue-50 text-blue-700 rounded-2xl text-xs border border-blue-200 hover:bg-blue-100 transition-colors">
              <div className="flex items-center gap-1">
                {getFileIcon(file)}
                <div className="flex flex-col">
                  <span className="truncate max-w-24 font-medium">{file.name}</span>
                  <span className="text-[10px] text-blue-500">{formatFileSize(file.size)}</span>
                </div>
              </div>
              <button
                onClick={() => removeFile(index)}
                  className="text-blue-500 hover:text-blue-700 p-1 rounded-full hover:bg-blue-200 transition-colors"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default EnhancedInput;
