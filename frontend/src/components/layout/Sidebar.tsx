import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { canAccess } from '../../lib/rbac';

export default function Sidebar() {
  const { role, logout } = useAuth();
  return (
    <aside style={{ width: '200px', borderRight: '1px solid var(--color-border)', padding: '1rem' }}>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <NavLink to="/">Dashboard</NavLink>
        <NavLink to="/messages">Messages</NavLink>
        {canAccess(role, 'admin') && <NavLink to="/users">Users</NavLink>}
        <button onClick={logout}>Logout</button>
      </nav>
    </aside>
  );
}
