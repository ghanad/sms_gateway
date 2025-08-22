import React from 'react';
import { useAuth } from '../hooks/useAuth';

export default function Dashboard() {
  const { user } = useAuth();
  return <div>Welcome, {user}</div>;
}
