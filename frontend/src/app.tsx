import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import Router from './router';
import { AppShell } from './components/layout/AppShell';
import { AuthProvider } from './hooks/useAuth';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppShell>
          <Router />
        </AppShell>
      </BrowserRouter>
    </AuthProvider>
  );
}
