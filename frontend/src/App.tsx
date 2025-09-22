import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Header } from './components';
import { ChatWithApproval, StreamingTutorial, Login, SignUp, ForgotPassword, UpdatePassword, AuthConfirm } from './pages';
import { AuthProvider } from './contexts/AuthContext';
import { UIStateProvider } from './contexts/UIStateContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import './App.css';

const AppContent: React.FC = () => {
  return (
    <div style={{ height: '100vh', backgroundColor: '#f9fafb', display: 'flex', flexDirection: 'column' }}>
      <Header />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', paddingTop: '6rem', minHeight: 0, overflow: 'auto' }}>
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