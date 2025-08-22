import React from 'react';
import { useAuth } from '../../hooks/useAuth';

export const Topbar = () => {
  const { user, logout } = useAuth();
  return (
    <header className="flex justify-between items-center border-b border-gray-300 px-4 py-2">
      <h1 className="text-xl">SMS Gateway</h1>
      {user && (
        <button onClick={logout} className="text-sm underline">
          Logout
        </button>
      )}
    </header>
  );
};
