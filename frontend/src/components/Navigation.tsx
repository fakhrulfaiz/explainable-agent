import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { MessageCircle, Users, Code } from 'lucide-react';

const Navigation: React.FC = () => {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Chat with Approval', icon: MessageCircle },
    { path: '/simple', label: 'Simple Chat', icon: Users },
    { path: '/demo', label: 'Demo', icon: Code },
  ];

  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-4xl mx-auto px-4">
        <div className="flex space-x-1">
          {navItems.map(({ path, label, icon: Icon }) => (
            <Link
              key={path}
              to={path}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium rounded-t-lg transition-colors ${
                location.pathname === path
                  ? 'bg-blue-50 text-blue-700 border-b-2 border-blue-700'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
};

export default Navigation;
