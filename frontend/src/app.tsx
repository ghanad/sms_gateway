import React from 'react';
import { AuthProvider } from './hooks/useAuth';
import AppRouter from './router';

export default function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}
