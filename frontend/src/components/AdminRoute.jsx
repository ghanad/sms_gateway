import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';

const AdminRoute = () => {
  const { user, isAuthenticated } = useAuth();
  return isAuthenticated && user?.isAdmin ? <Outlet /> : <Navigate to="/" replace />;
};

export default AdminRoute;
