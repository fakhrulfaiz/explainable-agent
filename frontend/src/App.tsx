import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
// import { Header } from './components';
import { ChatWithApproval, StreamingTutorial, Login, SignUp, ForgotPassword, UpdatePassword, AuthConfirm } from './pages';
import { AuthProvider } from './contexts/AuthContext';
import { UIStateProvider, useUIState } from './contexts/UIStateContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import './App.css';

const AppContent: React.FC = () => {
  const { state } = useUIState();
  const { isDarkMode } = state;

  // Apply dark mode class to document when state changes
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  // Initialize dark mode on mount
  useEffect(() => {
 
  }, []);

  return (
    <div className={`h-screen flex flex-col transition-colors duration-200 ${
      isDarkMode 
        ? 'bg-neutral-800 text-white' 
        : 'bg-gray-50 text-gray-900'
    }`}>
      <div className="flex-1 flex flex-col min-h-0">
        <Routes>
          {/* 🟢 Public routes - anyone can access */}
          <Route path="/login" element={<Login />} />
          <Route path="/sign-up" element={<SignUp />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/update-password" element={<UpdatePassword />} />
          <Route path="/auth/confirm" element={<AuthConfirm />} />
          
          {/* 🔒 Protected routes - only logged in users can access */}
          <Route path="/" element={
            <ProtectedRoute>
              <ChatWithApproval />
            </ProtectedRoute>
          } />
          
          <Route path="/streaming" element={
            <ProtectedRoute>
              <StreamingTutorial />
            </ProtectedRoute>
          } />
        </Routes>
      </div>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AuthProvider>
        <UIStateProvider>
          <AppContent />
        </UIStateProvider>
      </AuthProvider>
    </Router>
  );
};

export default App;