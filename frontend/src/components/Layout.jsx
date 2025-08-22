import React from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';

const Layout = () => {
  const { logout, user } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between whitespace-nowrap border-b border-gray-200 px-10 py-3">
        <h1 className="text-lg font-bold text-gray-900">SMS Gateway</h1>
        <nav className="flex gap-9 text-gray-900 items-center">
          <Link className="text-sm font-medium" to="/">Dashboard</Link>
          <Link className="text-sm font-medium" to="/messages">Messages</Link>
          {user?.isAdmin && (
            <Link className="text-sm font-medium" to="/admin/users">Users</Link>
          )}
          <button className="text-sm font-medium" onClick={handleLogout}>Logout</button>
        </nav>
      </header>
      <main className="flex-1 px-40 py-5">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
