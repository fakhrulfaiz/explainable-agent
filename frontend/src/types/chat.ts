export interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  needsApproval?: boolean;
  approved?: boolean;
  disapproved?: boolean;
  isError?: boolean;
  isFeedback?: boolean;
  isStreaming?: boolean;
  hasTimedOut?: boolean;
  canRetry?: boolean;
  retryAction?: 'approve' | 'feedback' | 'cancel';
  threadId?: string;
  messageType?: 'message' | 'explorer';
  checkpointId?: string;
  // New fields for rich content
  metadata?: {
    explorerData?: any;
    [key: string]: any;
  };
}

// Response object that handlers can return
export interface HandlerResponse {
  message: string;
  needsApproval?: boolean;
  explorerData?: any;
  // New streaming properties
  isStreaming?: boolean;
  streamingHandler?: (
    streamingMessageId: number, 
    updateMessageCallback: (id: number, content: string) => void,
    onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error' | 'tool_call' | 'tool_result', eventData?: string) => void
  ) => Promise<void>;
}


export interface ChatComponentProps {
  onSendMessage: (message: string, messageHistory: Message[]) => Promise<HandlerResponse>;
  onApprove?: (content: string, message: Message) => Promise<HandlerResponse | void> | HandlerResponse | void;
  onFeedback?: (content: string, message: Message) => Promise<HandlerResponse | void> | HandlerResponse | void;
  onCancel?: (content: string, message: Message) => Promise<string> | string;
  onRetry?: (message: Message) => Promise<HandlerResponse | void> | HandlerResponse | void;
  currentThreadId?: string | null;
  initialMessages?: Message[];
  className?: string;
  placeholder?: string;
  disabled?: boolean;
  onMessageCreated?: (message: Message) => void;
}

export interface MessageComponentProps {
  message: Message;
  onRetry?: (messageId: number) => void;
}

export interface FeedbackFormProps {
  feedbackText: string;
  setFeedbackText: (text: string) => void;
  onSendFeedback: () => void;
  onCancel: () => void;
  isLoading: boolean;
}

// Graph API Types
export interface StartRequest {
  human_request: string;
  thread_id?: string; // Optional thread ID for existing conversations
}

export interface ResumeRequest {
  thread_id: string;
  review_action: 'approved' | 'feedback' | 'cancelled';
  human_comment?: string;
}

export interface StepExplanation {
  id: number;
  type: string;
  decision: string;
  reasoning: string;
  input: string;
  output: string;
  confidence: number;
  why_chosen: string;
  timestamp: string;
}

export interface FinalResult {
  Summary: string;
  details: string;
  source: string;
  inference: string;
  extra_explanation: string;
}

export interface GraphResponse {
  thread_id: string;
  run_status: 'user_feedback' | 'finished' | 'error';
  assistant_response?: string;
  query?: string;  // User's original question
  plan?: string;
  error?: string;
  steps?: StepExplanation[];
  final_result?: FinalResult;
  total_time?: number;
  overall_confidence?: number;
}

export interface GraphStatus {
  thread_id: string;
  execution_status: string; // Graph execution state: 'user_feedback', 'running', 'finished'
  next_nodes: string[];
  plan: string;
  step_count: number;
  approval_status: string; // Agent approval state: 'approved', 'feedback', 'cancelled'
}