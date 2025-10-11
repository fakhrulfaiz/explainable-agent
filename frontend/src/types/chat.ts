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
  messageType?: 'message' | 'explorer' | 'visualization';
  checkpointId?: string;
  // New fields for rich content
  metadata?: {
    explorerData?: any;
    visualizations?: any[];
    [key: string]: any;
  };
}

// Response object that handlers can return
export interface HandlerResponse {
  message: string;
  needsApproval?: boolean;
  explorerData?: any;
  visualizations?: any[];
  checkpoint_id?: string; // Add checkpoint ID for both explorer and visualization messages
  response_type?: 'answer' | 'replan' | 'cancel';  // Type of response from backend
  // New streaming properties
  isStreaming?: boolean;
  streamingHandler?: (
    streamingMessageId: number, 
    updateMessageCallback: (id: number, content: string) => void,
    onStatus?: (status: 'user_feedback' | 'finished' | 'running' | 'error' | 'tool_call' | 'tool_result', eventData?: string, responseType?: 'answer' | 'replan' | 'cancel') => void
  ) => Promise<void>;
}


export interface ChatComponentProps {
  onSendMessage: (message: string, messageHistory: Message[], options?: { usePlanning?: boolean; useExplainer?: boolean; attachedFiles?: File[] }) => Promise<HandlerResponse>;
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
  use_planning?: boolean; // Whether to use planning in agent execution
  use_explainer?: boolean; // Whether to use explainer node for step explanations
  agent_type?: string; // Type of agent to use
}

export interface ResumeRequest {
  thread_id: string;
  review_action: 'approved' | 'feedback' | 'cancelled';
  human_comment?: string;
}

export interface StepExplanation {
  id: number;
  type: string;
  input: string;
  output: string;
  timestamp: string;
  decision?: string;
  reasoning?: string;
  confidence?: number;
  why_chosen?: string;
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
  checkpoint_id?: string; // Add checkpoint ID field
  run_status: 'user_feedback' | 'finished' | 'error';
  assistant_response?: string;
  query?: string;  // User's original question
  plan?: string;
  error?: string;
  steps?: StepExplanation[];
  final_result?: FinalResult;
  total_time?: number;
  overall_confidence?: number;
  response_type?: 'answer' | 'replan' | 'cancel';  // Type of response from planner
  visualizations?: any[]; // Visualization specs for frontend rendering
}

export interface GraphStatus {
  thread_id: string;
  execution_status: string; // Graph execution state: 'user_feedback', 'running', 'finished'
  next_nodes: string[];
  plan: string;
  step_count: number;
  approval_status: string; // Agent approval state: 'approved', 'feedback', 'cancelled'
}