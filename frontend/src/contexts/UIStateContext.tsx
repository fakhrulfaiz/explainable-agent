import React, { createContext, useContext, useReducer, ReactNode } from 'react';

// UI State Types
export type ExecutionStatus = 'idle' | 'running' | 'user_feedback' | 'finished' | 'error' | 'cancelled';

export interface UIState {

  executionStatus: ExecutionStatus;
  currentThreadId: string | null;
  
  // Loading state
  isLoading: boolean;
  
  // Streaming preference
  useStreaming: boolean;
  
  // Dark mode preference
  isDarkMode: boolean;
}

export type UIAction = 
  | { type: 'SET_EXECUTION_STATUS'; payload: ExecutionStatus }
  | { type: 'SET_THREAD_ID'; payload: string | null }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_USE_STREAMING'; payload: boolean }
  | { type: 'SET_DARK_MODE'; payload: boolean }
  | { type: 'RESET_STATE' };

// Load dark mode preference from localStorage
const getInitialDarkMode = () => {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem('darkMode');
    return saved === 'true';
  }
  return false;
};

const initialState: UIState = {
  executionStatus: 'idle',
  currentThreadId: null,
  isLoading: false,
  useStreaming: true,
  isDarkMode: getInitialDarkMode(),
};

function uiStateReducer(state: UIState, action: UIAction): UIState {
  switch (action.type) {
    case 'SET_EXECUTION_STATUS':
      return { ...state, executionStatus: action.payload };
    
    case 'SET_THREAD_ID':
      return { ...state, currentThreadId: action.payload };
    
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    
    case 'SET_USE_STREAMING':
      return { ...state, useStreaming: action.payload };
    
    case 'SET_DARK_MODE':
      return { ...state, isDarkMode: action.payload };
    
    case 'RESET_STATE':
      return initialState;
    
    default:
      return state;
  }
}

interface UIStateContextType {
  state: UIState;
  dispatch: React.Dispatch<UIAction>;
  
  // Convenience methods - only the essential ones
  setExecutionStatus: (status: ExecutionStatus) => void;
  setThreadId: (threadId: string | null) => void;
  setLoading: (loading: boolean) => void;
  setUseStreaming: (useStreaming: boolean) => void;
  setDarkMode: (isDarkMode: boolean) => void;
  resetState: () => void;
}

const UIStateContext = createContext<UIStateContextType | undefined>(undefined);

export function UIStateProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(uiStateReducer, initialState);

  const setExecutionStatus = (status: ExecutionStatus) => 
    dispatch({ type: 'SET_EXECUTION_STATUS', payload: status });
  
  const setThreadId = (threadId: string | null) => 
    dispatch({ type: 'SET_THREAD_ID', payload: threadId });
  
  const setLoading = (loading: boolean) => 
    dispatch({ type: 'SET_LOADING', payload: loading });
  
  const setUseStreaming = (useStreaming: boolean) =>
    dispatch({ type: 'SET_USE_STREAMING', payload: useStreaming });
  
  const setDarkMode = (isDarkMode: boolean) =>
    dispatch({ type: 'SET_DARK_MODE', payload: isDarkMode });
  
  const resetState = () => dispatch({ type: 'RESET_STATE' });

  const value: UIStateContextType = {
    state,
    dispatch,
    setExecutionStatus,
    setThreadId,
    setLoading,
    setUseStreaming,
    setDarkMode,
    resetState,
  };

  return (
    <UIStateContext.Provider value={value}>
      {children}
    </UIStateContext.Provider>
  );
}

export function useUIState() {
  const context = useContext(UIStateContext);
  if (context === undefined) {
    throw new Error('useUIState must be used within a UIStateProvider');
  }
  return context;
}
