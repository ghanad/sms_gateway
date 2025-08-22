import React from 'react';
import { NavLink } from 'react-router-dom';

export const Sidebar = () => (
  <nav className="w-48 border-r border-gray-300 p-4">
    <ul className="space-y-2">
      <li>
        <NavLink to="/dashboard">Dashboard</NavLink>
      </li>
      <li>
        <NavLink to="/messages">Messages</NavLink>
      </li>
      <li>
        <NavLink to="/users">Users</NavLink>
      </li>
    </ul>
  </nav>
);
