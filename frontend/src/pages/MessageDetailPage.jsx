import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import apiService from '../services/apiService.js';

const MessageDetailPage = () => {
  const { trackingId } = useParams();
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMessage = async () => {
      try {
        const data = await apiService.getMessageDetails(trackingId);
        setMessage(data);
      } catch {
        setError('Failed to load message');
      } finally {
        setLoading(false);
      }
    };
    fetchMessage();
  }, [trackingId]);

  if (loading) return <p className="p-4">Loading...</p>;
  if (error) return <p className="p-4 text-red-500">{error}</p>;

  return (
    <div className="layout-content-container flex flex-col max-w-[960px] mx-auto">
      <div className="flex flex-wrap gap-2 p-4">
        <Link to="/messages" className="text-gray-500 text-base font-medium">Messages</Link>
        <span className="text-gray-500 text-base font-medium">/</span>
        <span className="text-gray-900 text-base font-medium">Message Details</span>
      </div>
      <div className="flex flex-wrap justify-between gap-3 p-4">
        <div className="flex min-w-72 flex-col gap-3">
          <p className="text-2xl font-bold text-gray-900">Message Details</p>
          <p className="text-sm text-gray-500">View the full history and details of a single message.</p>
        </div>
      </div>
      <h2 className="text-xl font-bold px-4 pb-3 pt-5">Message Details</h2>
      <div className="p-4 grid grid-cols-2 gap-x-4">
        <div className="flex flex-col gap-1 border-t border-gray-300 py-4 pr-2">
          <p className="text-sm text-gray-500">Message ID</p>
          <p className="text-sm text-gray-900">{message.id || message.message_id || 'N/A'}</p>
        </div>
        <div className="flex flex-col gap-1 border-t border-gray-300 py-4 pl-2">
          <p className="text-sm text-gray-500">Recipient</p>
          <p className="text-sm text-gray-900">{message.recipient}</p>
        </div>
        <div className="flex flex-col gap-1 border-t border-gray-300 py-4 pr-2">
          <p className="text-sm text-gray-500">Sender</p>
          <p className="text-sm text-gray-900">{message.sender || '-'}</p>
        </div>
        <div className="flex flex-col gap-1 border-t border-gray-300 py-4 pl-2">
          <p className="text-sm text-gray-500">Status</p>
          <p className="text-sm text-gray-900 capitalize">{message.status}</p>
        </div>
        <div className="flex flex-col gap-1 border-t border-gray-300 py-4 pr-2">
          <p className="text-sm text-gray-500">Sent At</p>
          <p className="text-sm text-gray-900">{message.created_at}</p>
        </div>
        <div className="flex flex-col gap-1 border-t border-gray-300 py-4 pl-2">
          <p className="text-sm text-gray-500">Delivered At</p>
          <p className="text-sm text-gray-900">{message.delivered_at || '-'}</p>
        </div>
        <div className="flex flex-col gap-1 border-t border-gray-300 py-4 pr-2 col-span-2">
          <p className="text-sm text-gray-500">Message Content</p>
          <p className="text-sm text-gray-900">{message.text}</p>
        </div>
      </div>
    </div>
  );
};

export default MessageDetailPage;
