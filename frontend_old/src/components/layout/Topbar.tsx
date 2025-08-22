import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

export const Topbar = () => {
  const { user, logout } = useAuth();
  return (
    <header className="flex justify-between items-center border-b border-gray-300 px-4 py-2">
      <h1 className="text-xl">SMS Gateway</h1>
      {user && (
        <div className="space-x-2">
          <Link to="/change-password" className="text-sm underline">
            Change Password
          </Link>
          <button onClick={logout} className="text-sm underline">
            Logout
          </button>
        </div>
      )}
    </header>
  );
};
