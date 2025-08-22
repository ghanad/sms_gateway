import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useFetch } from '../hooks/useFetch';
import { formatDate } from '../lib/format';

export default function MessageDetail() {
  const { id } = useParams();
  const fetcher = useFetch();
  const [message, setMessage] = useState<any | null>(null);

  useEffect(() => {
    fetcher(`/api/messages/${id}`)
      .then(setMessage)
      .catch(() => setMessage(null));
  }, [id]);

  if (!message) return <p>Not found</p>;

  return (
    <div>
      <h2>Message {message.id}</h2>
      <p>To: {message.to}</p>
      <p>Status: {message.status}</p>
      <p>Created: {formatDate(message.created)}</p>
    </div>
  );
}
