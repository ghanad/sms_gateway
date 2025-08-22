import React from 'react';

interface AuthContextProps {
  user: string | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = React.createContext<AuthContextProps | undefined>(undefined);

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [token, setToken] = React.useState<string | null>(
    localStorage.getItem('token')
  );
  const [user, setUser] = React.useState<string | null>(
    localStorage.getItem('user')
  );

  const login = async (username: string, password: string) => {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (res.ok) {
      const data = await res.json();
      setToken(data.access_token);
      setUser(username);
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user', username);
    } else {
      throw new Error('Login failed');
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  };

  return React.createElement(
    AuthContext.Provider,
    { value: { user, token, login, logout, isAuthenticated: !!token } },
    children
  );
};

export const useAuth = () => {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
