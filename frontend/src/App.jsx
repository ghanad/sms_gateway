import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import AdminRoute from './components/AdminRoute.jsx';
import LoginPage from './pages/LoginPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import MessageHistoryPage from './pages/MessageHistoryPage.jsx';
import MessageDetailPage from './pages/MessageDetailPage.jsx';
import UserManagementPage from './pages/admin/UserManagementPage.jsx';
import { AuthProvider } from './context/AuthContext.jsx';

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Layout />}>
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/messages" element={<MessageHistoryPage />} />
              <Route path="/messages/:trackingId" element={<MessageDetailPage />} />
              <Route element={<AdminRoute />}>
                <Route path="/admin/users" element={<UserManagementPage />} />
              </Route>
            </Route>
          </Route>
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
