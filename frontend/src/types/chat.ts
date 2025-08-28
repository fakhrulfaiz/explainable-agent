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
  hasTimedOut?: boolean;
  canRetry?: boolean;
  retryAction?: 'approve' | 'disapprove' | 'cancel';
  threadId?: string;
}

export interface ChatComponentProps {
  onSendMessage: (message: string, messageHistory: Message[]) => Promise<string>;
  onApprove?: (content: string, message: Message) => Promise<string | void> | string | void;
  onDisapprove?: (content: string, message: Message) => Promise<string | void> | string | void;
  onCancel?: (content: string, message: Message) => Promise<string | void> | string | void;
  onRetry?: (message: Message) => Promise<string | void> | string | void;
  onMessageCreated?: (messageId: number) => void;
  currentThreadId?: string | null;
  className?: string;
  placeholder?: string;
  showApprovalButtons?: boolean;
  disabled?: boolean;
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
  plan?: string;
  error?: string;
  steps?: StepExplanation[];
  final_result?: FinalResult;
  total_time?: number;
  overall_confidence?: number;
}

export interface GraphStatus {
  thread_id: string;
  status: string;
  next_nodes: string[];
  plan: string;
  step_count: number;
  current_status: string;
}