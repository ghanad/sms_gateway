import React, { useEffect, useState } from 'react';
import Table from '../components/ui/Table';
import { useFetch } from '../hooks/useFetch';
import { Link } from 'react-router-dom';
import { formatDate } from '../lib/format';

export default function MessagesList() {
  const fetcher = useFetch();
  const [messages, setMessages] = useState<any[]>([]);

  useEffect(() => {
    fetcher('/api/messages')
      .then(setMessages)
      .catch(() => setMessages([]));
  }, []);

  return (
    <div>
      <h2>Messages</h2>
      <Table
        headers={['ID', 'To', 'Status', 'Created']}
        rows={messages.map(m => [
          <Link to={`/messages/${m.id}`}>{m.id}</Link>,
          m.to,
          m.status,
          formatDate(m.created)
        ])}
      />
    </div>
  );
}
