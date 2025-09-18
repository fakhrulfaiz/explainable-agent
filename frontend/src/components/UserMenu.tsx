import React from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from './ui/button';
import { useNavigate } from 'react-router-dom';

export const UserMenu: React.FC = () => {
  const { user, signOut, loading } = useAuth();
  const navigate = useNavigate();

  if (loading) {
    return <div className="text-sm text-gray-500">Loading...</div>;
  }

  if (!user) {
    return (
      <div className="flex gap-2">
        <Button variant="outline" onClick={() => navigate('/login')}>
          Login
        </Button>
        <Button onClick={() => navigate('/sign-up')}>
          Sign Up
        </Button>
      </div>
    );
  }

  const handleSignOut = async () => {
    await signOut();
    navigate('/login');
  };

  return (
    <div className="flex items-center gap-3">
      <div className="text-sm text-gray-700">
        Welcome, {user.email}
      </div>
      <Button variant="outline" onClick={handleSignOut} size="sm">
        Sign Out
      </Button>
    </div>
  );
};
