import React, { createContext, useContext, useState } from 'react';
import apiService from '../services/apiService.js';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('user');
    if (stored && stored !== 'undefined') {
      return JSON.parse(stored);
    }
    return null;
  });
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const isAuthenticated = !!token;

  const login = async (username, password) => {
    const data = await apiService.login(username, password);
    const payload = JSON.parse(atob(data.token.split('.')[1]));
    const userInfo = { username: payload.username, id: payload.user_id, isAdmin: payload.is_admin };
    setUser(userInfo);
    setToken(data.token);
    localStorage.setItem('user', JSON.stringify(userInfo));
    localStorage.setItem('token', data.token);
  };

    const logout = async () => {
      await apiService.logout();
      setUser(null);
      setToken(null);
      localStorage.removeItem('user');
      localStorage.removeItem('token');
    };

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
