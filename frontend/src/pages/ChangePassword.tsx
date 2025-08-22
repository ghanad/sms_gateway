import React from 'react';
import { changePassword } from '../api/users';
import { useAuth } from '../hooks/useAuth';

export default function ChangePassword() {
  const { user } = useAuth();
  const [password, setPassword] = React.useState('');
  const [message, setMessage] = React.useState('');

  if (!user) return <div>Loading...</div>;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await changePassword(user, password);
    setMessage('Password updated');
    setPassword('');
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 space-y-2">
      <input
        type="password"
        placeholder="New Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button type="submit">Change Password</button>
      {message && <div>{message}</div>}
    </form>
  );
}
