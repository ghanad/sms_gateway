import React from 'react';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import MessagesList from './pages/MessagesList';
import MessageDetail from './pages/MessageDetail';
import UsersAdmin from './pages/UsersAdmin';
import NotFound from './pages/NotFound';
import { RequireAuth } from './hooks/useAuth';

const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'messages', element: <MessagesList /> },
      { path: 'messages/:id', element: <MessageDetail /> },
      { path: 'users', element: <UsersAdmin /> },
      { path: '*', element: <NotFound /> }
    ]
  },
  { path: '/login', element: <Login /> }
]);

export default function AppRouter() {
  return <RouterProvider router={router} />;
}
