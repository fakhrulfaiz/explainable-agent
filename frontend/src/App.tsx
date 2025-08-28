import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Header } from './components';
import { ChatWithApproval, SimpleChat, Demo, StreamingTutorial } from './pages';
import './App.css';

const AppContent: React.FC = () => {
  return (
    <div style={{ height: '100vh', backgroundColor: '#f9fafb', display: 'flex', flexDirection: 'column' }}>
      <Header />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', paddingTop: '1rem' }}>
        <Routes>
          <Route path="/" element={<ChatWithApproval />} />
          <Route path="/simple" element={<SimpleChat />} />
          <Route path="/demo" element={<Demo />} />
          <Route path="/streaming" element={<StreamingTutorial />} />
        </Routes>
      </div>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AppContent />
    </Router>
  );
};

export default App;