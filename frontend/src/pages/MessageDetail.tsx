import React from 'react';
import { useParams } from 'react-router-dom';
import { useFetch } from '../hooks/useFetch';
import { API_BASE_URL } from '../api/client';
import { Message } from '../api/messages';

export default function MessageDetail() {
  const { id } = useParams();
  const { data } = useFetch<Message>(`${API_BASE_URL}/api/messages/${id}`);
  if (!data) return <div>Loading...</div>;
  return (
    <div>
      <h2 className="text-xl mb-2">Message {data.id}</h2>
      <p>{data.content}</p>
      <p>Status: {data.status}</p>
    </div>
  );
}
