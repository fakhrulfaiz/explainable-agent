import React, { useState, useRef } from 'react';
import { ArrowUp, Upload, X, Check, Brain, Zap, Layers, File, Image, FileText, FileCode, Plus } from 'lucide-react';
import { useUIState } from '../contexts/UIStateContext';
import {
  InputGroup,
  InputGroupTextarea,
  InputGroupAddon,
  InputGroupButton,
  InputGroupText,
} from '@/components/ui/input-group';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { Separator } from '@/components/ui/separator';
import LLMSelector from './LLMSelector';

interface InputFormProps {
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

const InputForm: React.FC<InputFormProps> = ({
  value,
  onChange,
  onSend,
  onKeyDown,
  placeholder = "Ask, Search or Chat...",
  disabled = false,
  isLoading = false,
  usePlanning = false,
  useExplainer = false,
  onPlanningToggle,
  onExplainerToggle,
  onFilesChange,
  attachedFiles = []
}) => {
  const { state, setUseStreaming } = useUIState();
  const useStreaming = state.useStreaming;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isTextareaExpanded, setIsTextareaExpanded] = useState<boolean>(false);

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
    <div className="w-full max-w-3xl mx-auto space-y-2">
      {/* Attached Files Display */}
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {attachedFiles.map((file, index) => (
            <div key={index} className="flex items-center gap-2 px-3 py-1.5 bg-accent text-accent-foreground rounded-full text-xs border border-border">
              <div className="flex items-center gap-1.5">
                {getFileIcon(file)}
                <div className="flex flex-col">
                  <span className="truncate max-w-32 font-medium">{file.name}</span>
                  <span className="text-[10px] text-muted-foreground">{formatFileSize(file.size)}</span>
                </div>
              </div>
              <button
                onClick={() => removeFile(index)}
                className="text-accent-foreground hover:bg-accent p-0.5 rounded-full transition-colors"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input Group */}
      <InputGroup className="rounded-3xl px-2 bg-muted">
        <InputGroupTextarea 
          ref={textareaRef}
          className={`rounded-3xl resize-none mt-1 max-h-64 min-h-[5rem] textarea-scroll bg-transparent text-foreground placeholder:text-muted-foreground ${
            isTextareaExpanded ? 'overflow-y-auto' : 'overflow-y-hidden'
          }`}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleTextareaKeyDown}
          onInput={handleTextareaInput}
          disabled={disabled || isLoading}
          rows={1}
        />
        <InputGroupAddon align="block-end">
          {/* Options Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
          <InputGroupButton
            variant="outline"
            className="rounded-xl"
            size="icon-sm"
          >
               <Plus className="w-4 h-4" strokeWidth={3}  />
              </InputGroupButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              side="top"
              align="start"
              className="[--radius:0.95rem] min-w-40"
              onMouseDown={(e) => e.preventDefault()}
            >
              <DropdownMenuItem onClick={(e) => {
                e.preventDefault();
                onPlanningToggle?.(!usePlanning);
              }}>
                <Layers className={`w-4 h-4 mr-2 ${usePlanning ? 'text-blue-600' : ''}`} />
                Planning
                {usePlanning && <Check className="w-4 h-4 ml-auto text-blue-600" />}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={(e) => {
                e.preventDefault();
                onExplainerToggle?.(!useExplainer);
              }}>
                <Brain className={`w-4 h-4 mr-2 ${useExplainer ? 'text-emerald-600' : ''}`} />
                Explainer
                {useExplainer && <Check className="w-4 h-4 ml-auto text-emerald-600" />}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={(e) => {
                e.preventDefault();
                setUseStreaming(!useStreaming);
              }}>
                <Zap className={`w-4 h-4 mr-2 ${useStreaming ? 'text-purple-600' : ''}`} />
                Streaming
                {useStreaming && <Check className="w-4 h-4 ml-auto text-purple-600" />}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={(e) => {
                e.preventDefault();
                fileInputRef.current?.click();
              }}>
                <Upload className="w-4 h-4 mr-2" />
                Upload File
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* LLM Selector */}
          <LLMSelector compact />

          <InputGroupText className="ml-auto text-muted-foreground">52% used</InputGroupText>
          
          <Separator orientation="vertical" className="!h-4" />
          
          {/* Send Button */}
          <InputGroupButton
            variant="default"
            className="rounded-xl"
            size="icon-sm"
            disabled={!value.trim() || disabled || isLoading}
            onClick={onSend}
          >
            <ArrowUp className="w-5 h-5 text-foreground" strokeWidth={3} />
            <span className="sr-only">Send</span>
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="image/*"
        onChange={handleFileUpload}
        className="hidden"
      />
    </div>
  );
};

export default InputForm;