import React from 'react';
import { useFetch } from '../hooks/useFetch';
import { API_BASE_URL } from '../api/client';
import { Table } from '../components/ui/Table';
import { Link } from 'react-router-dom';
import { Message } from '../api/messages';

export default function MessagesList() {
  const { data } = useFetch<Message[]>(`${API_BASE_URL}/api/messages`);
  if (!data) return <div>Loading...</div>;
  const rows = data.map((m) => [
    <Link key={m.id} to={`/messages/${m.id}`}>{m.id}</Link>,
    m.content,
    m.status,
  ]);
  return <Table headers={["ID", "Content", "Status"]} rows={rows} />;
}
