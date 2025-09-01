import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { MessageCircle, Users, Code, Bot, Menu, X } from 'lucide-react';

// Custom hook for window size
const useWindowSize = () => {
  const [windowSize, setWindowSize] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 1200,
  });

  useEffect(() => {
    const handleResize = () => {
      setWindowSize({
        width: window.innerWidth,
      });
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return windowSize;
};

const Header: React.FC = () => {
  const location = useLocation();
  const { width } = useWindowSize();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const isMobile = width < 768;

  const navItems = [
    { path: '/', label: 'Chat with Approval', icon: MessageCircle },
    { path: '/simple', label: 'Simple Chat', icon: Users },
    { path: '/demo', label: 'Demo', icon: Code },
    { path: '/streaming', label: 'Streaming Tutorial', icon: Code },
  ];

  return (
    <header style={{
      backgroundColor: 'white',
      borderBottom: '1px solid #e5e7eb',
      boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
      width: '100%',
      position: 'fixed',
      zIndex: 1000
    }}>
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '0 0.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '4rem'
      }}>
        {/* Logo */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: width < 768 ? '0.5rem' : '0.75rem',
          color: '#1f2937',
          fontSize: width < 768 ? '1rem' : '1.25rem',
          fontWeight: '600'
        }}>
          <Bot style={{ 
            color: '#2563eb', 
            width: width < 768 ? '1.5rem' : '2rem', 
            height: width < 768 ? '1.5rem' : '2rem' 
          }} />
          <h1 style={{ 
            margin: 0, 
            fontSize: width < 768 ? '1rem' : '1.25rem', 
            fontWeight: '700',
            display: width < 480 ? 'none' : 'block'
          }}>
            {width < 768 ? " " : 'Explainable Agent'}
          </h1>
        </div>
        
        {/* Navigation */}
        {isMobile ? (
          /* Mobile: Hamburger Menu */
          <div>
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              style={{
                padding: '0.5rem',
                backgroundColor: 'transparent',
                border: 'none',
                color: '#4b5563',
                cursor: 'pointer',
                borderRadius: '0.375rem'
              }}
            >
              {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>
        ) : (
          /* Desktop: Normal Navigation */
          <nav style={{
            display: 'flex',
            gap: '0.5rem'
          }}>
            {navItems.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.5rem 1rem',
                  borderRadius: '0.5rem',
                  color: location.pathname === path ? '#1d4ed8' : '#4b5563',
                  backgroundColor: location.pathname === path ? '#dbeafe' : 'transparent',
                  textDecoration: 'none',
                  fontSize: '0.875rem',
                  fontWeight: '500',
                  transition: 'all 0.2s',
                  border: 'none'
                }}
                onMouseEnter={(e) => {
                  if (location.pathname !== path) {
                    e.currentTarget.style.backgroundColor = '#f3f4f6';
                    e.currentTarget.style.color = '#1f2937';
                  }
                }}
                onMouseLeave={(e) => {
                  if (location.pathname !== path) {
                    e.currentTarget.style.backgroundColor = 'transparent';
                    e.currentTarget.style.color = '#4b5563';
                  }
                }}
              >
                <Icon size={16} />
                {label}
              </Link>
            ))}
          </nav>
        )}
      </div>
      
      {/* Mobile Menu Dropdown */}
      {isMobile && isMobileMenuOpen && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          backgroundColor: 'white',
          borderTop: '1px solid #e5e7eb',
          boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
          zIndex: 50
        }}>
          <nav style={{
            display: 'flex',
            flexDirection: 'column',
            padding: '0.5rem 0'
          }}>
            {navItems.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                onClick={() => setIsMobileMenuOpen(false)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '0.75rem 1rem',
                  color: location.pathname === path ? '#1d4ed8' : '#374151',
                  backgroundColor: location.pathname === path ? '#eff6ff' : 'transparent',
                  textDecoration: 'none',
                  fontSize: '1rem',
                  fontWeight: '500',
                  borderLeft: location.pathname === path ? '3px solid #1d4ed8' : '3px solid transparent',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  if (location.pathname !== path) {
                    e.currentTarget.style.backgroundColor = '#f9fafb';
                  }
                }}
                onMouseLeave={(e) => {
                  if (location.pathname !== path) {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }
                }}
              >
                <Icon size={20} />
                {label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
};

export default Header;
