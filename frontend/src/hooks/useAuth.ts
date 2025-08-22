import React, { createContext, useContext, useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { login as apiLogin } from '../api/auth';

interface AuthState {
  token: string | null;
  role: string | null;
}

interface AuthContext extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthCtx = createContext<AuthContext>({
  token: null,
  role: null,
  login: async () => {},
  logout: () => {}
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem('auth');
    if (stored) {
      const obj = JSON.parse(stored);
      setToken(obj.token);
      setRole(obj.role);
    }
  }, []);

  useEffect(() => {
    if (token) {
      localStorage.setItem('auth', JSON.stringify({ token, role }));
    } else {
      localStorage.removeItem('auth');
    }
  }, [token, role]);

  const login = async (username: string, password: string) => {
    const res = await apiLogin(username, password);
    setToken(res.access_token);
    setRole(res.role);
  };

  const logout = () => {
    setToken(null);
    setRole(null);
  };

  return (
    <AuthCtx.Provider value={{ token, role, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
};

export function useAuth() {
  return useContext(AuthCtx);
}

export const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token } = useAuth();
  const location = useLocation();
  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
};
