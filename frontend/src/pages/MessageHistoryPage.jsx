import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import apiService from '../services/apiService.js';

const MessageHistoryPage = () => {
  const [filters, setFilters] = useState({
    startDate: '',
    endDate: '',
    status: '',
    recipient: '',
    trackingId: ''
  });
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchMessages = async () => {
    setLoading(true);
    try {
      const params = {
        startDate: filters.startDate || undefined,
        endDate: filters.endDate || undefined,
        status: filters.status || undefined,
        recipient: filters.recipient || undefined,
        tracking_id: filters.trackingId || undefined
      };
      const data = await apiService.getMessages(params);
      setMessages(data.items || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMessages();
  }, []);

  const handleReset = () => {
    setFilters({ startDate: '', endDate: '', status: '', recipient: '', trackingId: '' });
    fetchMessages();
  };

  return (
    <div className="layout-content-container flex flex-col max-w-[960px] mx-auto">
      <div className="flex flex-wrap justify-between gap-3 p-4">
        <div className="flex min-w-72 flex-col gap-3">
          <p className="text-2xl font-bold text-gray-900">Messages</p>
          <p className="text-sm text-gray-500">View and manage all messages sent through the SMS Gateway.</p>
        </div>
      </div>
      <h3 className="text-lg font-bold px-4 pb-2 pt-4">Filters</h3>
      <div className="flex flex-col p-4 gap-3">
        <details className="flex flex-col rounded-lg border border-gray-300 bg-white px-3 py-1 group">
          <summary className="flex cursor-pointer items-center justify-between gap-6 py-1">
            <p className="text-sm font-medium text-gray-900">Show Filters</p>
            <span className="text-gray-900 group-open:rotate-180">&#9660;</span>
          </summary>
          <div className="grid grid-cols-1 md:grid-cols-6 gap-2 pt-2 pb-1">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Start date</label>
              <input
                type="date"
                className="h-9 rounded-md border border-gray-300 px-2 text-sm"
                value={filters.startDate}
                onChange={(e) => setFilters({ ...filters, startDate: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">End date</label>
              <input
                type="date"
                className="h-9 rounded-md border border-gray-300 px-2 text-sm"
                value={filters.endDate}
                onChange={(e) => setFilters({ ...filters, endDate: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Status</label>
              <select
                className="h-9 rounded-md border border-gray-300 px-2 text-sm bg-white"
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              >
                <option value="">All</option>
                <option value="sent">Sent</option>
                <option value="delivered">Delivered</option>
                <option value="failed">Failed</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Recipient phone number</label>
              <input
                type="tel"
                placeholder="e.g. +15551234567"
                className="h-9 rounded-md border border-gray-300 px-2 text-sm"
                value={filters.recipient}
                onChange={(e) => setFilters({ ...filters, recipient: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Tracking ID</label>
              <input
                type="text"
                placeholder="e.g. ABC123XYZ"
                className="h-9 rounded-md border border-gray-300 px-2 text-sm"
                value={filters.trackingId}
                onChange={(e) => setFilters({ ...filters, trackingId: e.target.value })}
              />
            </div>
            <div className="flex items-end gap-2 md:justify-end">
              <button
                onClick={fetchMessages}
                className="h-9 px-3 rounded-md bg-black text-white text-xs"
              >
                Apply
              </button>
              <button
                onClick={handleReset}
                className="h-9 px-3 rounded-md bg-gray-200 text-xs text-gray-900"
              >
                Reset
              </button>
            </div>
          </div>
        </details>
      </div>
      <h3 className="text-lg font-bold px-4 pb-2 pt-4">Message List</h3>
      <div className="px-4 py-3">
        <div className="overflow-hidden rounded-lg border border-gray-300 bg-white">
          <table className="min-w-full">
            <thead>
              <tr className="bg-white text-left text-sm font-medium text-gray-900">
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Recipient</th>
                <th className="px-4 py-3">Message</th>
                <th className="px-4 py-3">Tracking ID</th>
              </tr>
            </thead>
            <tbody>
              {messages.map((msg) => (
                <tr key={msg.tracking_id} className="border-t">
                  <td className="px-4 py-2 text-sm text-gray-500">{msg.created_at}</td>
                  <td className="px-4 py-2 text-sm">
                    <span className="bg-gray-200 rounded px-2 py-1 capitalize">{msg.status}</span>
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-500">{msg.recipient}</td>
                  <td className="px-4 py-2 text-sm text-gray-500">{msg.text}</td>
                  <td className="px-4 py-2 text-sm text-blue-600">
                    <Link to={`/messages/${msg.tracking_id}`}>{msg.tracking_id}</Link>
                  </td>
                </tr>
              ))}
              {messages.length === 0 && !loading && (
                <tr>
                  <td colSpan="5" className="px-4 py-2 text-center text-sm text-gray-500">
                    No messages found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default MessageHistoryPage;
