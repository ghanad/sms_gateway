import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import { useNavigate, useLocation } from 'react-router-dom';

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation() as any;
  const from = location.state?.from?.pathname || '/';

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError('Login failed');
    }
  };

  return (
    <div style={{ maxWidth: '300px', margin: '3rem auto' }}>
      <h2>Login</h2>
      <form onSubmit={onSubmit}>
        <div style={{ marginBottom: '0.5rem' }}>
          <Input placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} />
        </div>
        <div style={{ marginBottom: '0.5rem' }}>
          <Input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} />
        </div>
        {error && <p role="alert">{error}</p>}
        <Button type="submit">Login</Button>
      </form>
    </div>
  );
}
