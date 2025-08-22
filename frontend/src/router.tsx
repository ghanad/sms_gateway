import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import MessagesList from './pages/MessagesList';
import MessageDetail from './pages/MessageDetail';
import UsersAdmin from './pages/UsersAdmin';
import NotFound from './pages/NotFound';
import { useAuth } from './hooks/useAuth';

export default function Router() {
  const { isAuthenticated } = useAuth();
  return (
    <Routes>
      <Route path="/" element={isAuthenticated ? <Dashboard /> : <Login />} />
      <Route path="/login" element={<Login />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/messages" element={<MessagesList />} />
      <Route path="/messages/:id" element={<MessageDetail />} />
      <Route path="/users" element={<UsersAdmin />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
