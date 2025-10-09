import React, { useState, useRef } from 'react';
import { Send, Plus, X, Upload, File, Image, FileText, FileCode, Zap } from 'lucide-react';
import { useUIState } from '../contexts/UIStateContext';

interface EnhancedInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  placeholder?: string;
  disabled?: boolean;
  isLoading?: boolean;
  usePlanning?: boolean;
  onPlanningToggle?: (enabled: boolean) => void;
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
  onPlanningToggle,
  onFilesChange,
  attachedFiles = []
}) => {
  const [showInputOptions, setShowInputOptions] = useState<boolean>(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Get streaming state from context
  const { state, setUseStreaming } = useUIState();
  const useStreaming = state.useStreaming;

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

  return (
    <div className="space-y-2">
      {/* Enhanced Input Options */}
      {showInputOptions && (
        <div className="p-2 bg-gray-50 rounded-lg border flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={togglePlanning}
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors h-7 w-26 ${
                usePlanning 
                  ? 'bg-blue-100 text-blue-700 border border-blue-200' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {usePlanning ? <X className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
              {usePlanning ? 'Planning On' : 'Planning Off'}
            </button>
            
            <button
              onClick={() => setUseStreaming(!useStreaming)}
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors h-7 w-28 ${
                useStreaming 
                  ? 'bg-purple-100 text-purple-700 border border-purple-200' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <Zap className="w-3 h-3" />
              {useStreaming ? 'Streaming On' : 'Streaming Off'}
            </button>
            
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1 px-2 py-1 rounded-md text-xs h-7 w-20 bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
            >
              <Upload className="w-3 h-3" />
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

      {/* Attached files are now shown in the options box above */}

      {/* Main Input Area */}
      <div className="flex gap-2">
        <div className="flex-1 relative text-base">
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            disabled={disabled || isLoading}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed text-gray-900 bg-white"
          />
          
          {/* Plus button for options */}
          <button
            onClick={toggleInputOptions}
            className="absolute right-2 top-1/2 transform -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 transition-colors"
          >
            {showInputOptions ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          </button>
        </div>
        
        <button
          onClick={onSend}
          disabled={!value.trim() || disabled || isLoading}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors text-base"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {attachedFiles.map((file, index) => (
            <div key={index} className="flex items-center gap-2 px-2 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs border border-blue-200 hover:bg-blue-100 transition-colors">
              <div className="flex items-center gap-1">
                {getFileIcon(file)}
                <div className="flex flex-col">
                  <span className="truncate max-w-24 font-medium">{file.name}</span>
                  <span className="text-[10px] text-blue-500">{formatFileSize(file.size)}</span>
                </div>
              </div>
              <button
                onClick={() => removeFile(index)}
                className="text-blue-500 hover:text-blue-700 p-1 rounded hover:bg-blue-200 transition-colors"
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
