import React from 'react';
import { useFetch } from '../hooks/useFetch';
import { API_BASE_URL } from '../api/client';
import { Table } from '../components/ui/Table';
import { User } from '../api/users';

export default function UsersAdmin() {
  const { data } = useFetch<User[]>(`${API_BASE_URL}/api/users`);
  if (!data) return <div>Loading...</div>;
  const rows = data.map((u) => [u.id, u.username, u.role]);
  return <Table headers={["ID", "Username", "Role"]} rows={rows} />;
}
