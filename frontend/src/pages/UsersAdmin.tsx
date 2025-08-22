import React, { useEffect, useState } from 'react';
import Table from '../components/ui/Table';
import { useFetch } from '../hooks/useFetch';
import { canAccess } from '../lib/rbac';
import { useAuth } from '../hooks/useAuth';

export default function UsersAdmin() {
  const fetcher = useFetch();
  const { role } = useAuth();
  const [users, setUsers] = useState<any[]>([]);

  useEffect(() => {
    fetcher('/api/users')
      .then(setUsers)
      .catch(() => setUsers([]));
  }, []);

  if (!canAccess(role, 'admin')) return <p>Access denied</p>;

  return (
    <div>
      <h2>Users</h2>
      <Table headers={['Username', 'Role']} rows={users.map(u => [u.username, u.role])} />
    </div>
  );
}
