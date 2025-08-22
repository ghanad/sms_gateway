import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import apiService from '../services/apiService.js';

const StatCard = ({ title, value, change, changeType }) => (
  <div className="flex-1 rounded-lg border border-[#dbe0e6] bg-white p-4">
    <p className="text-sm text-[#60758a]">{title}</p>
    <p className="text-2xl font-bold text-[#111418]">{value}</p>
  </div>
);

const DashboardPage = () => {
  const [stats, setStats] = useState({ total: 0, sent: 0, delivered: 0, failed: 0 });
  const [recentMessages, setRecentMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [statsData, messagesData] = await Promise.all([
          apiService.getDashboardStats(),
          apiService.getMessages({ limit: 5 })
        ]);
        setStats(statsData);
        setRecentMessages(messagesData.items || []);
      } catch (err) {
        setError('Failed to load dashboard data.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (error) {
    return <div className="text-center text-red-500 p-4">{error}</div>;
  }

  return (
    <div className="layout-content-container flex flex-col max-w-[960px] mx-auto">
      <div className="flex flex-wrap justify-between gap-3 p-4">
        <div className="flex min-w-72 flex-col gap-3">
          <p className="text-2xl font-bold text-gray-900">Dashboard</p>
          <p className="text-sm text-gray-500">Overview of your SMS gateway activity.</p>
        </div>
      </div>

      {loading ? (
        <div className="text-center p-4">Loading...</div>
      ) : (
        <>
          <h3 className="text-lg font-bold px-4 pb-2 pt-4">Statistics</h3>
          <div className="flex flex-wrap gap-4 p-4">
            <StatCard title="Total Messages" value={stats.total} />
            <StatCard title="Sent" value={stats.sent} />
            <StatCard title="Delivered" value={stats.delivered} />
            <StatCard title="Failed" value={stats.failed} />
          </div>

          <h3 className="text-lg font-bold px-4 pb-2 pt-4">Recent Messages</h3>
          <div className="px-4 py-3">
            <div className="overflow-hidden rounded-lg border border-gray-300 bg-white">
              <table className="min-w-full">
                <thead>
                  <tr className="bg-white text-left text-sm font-medium text-gray-900">
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Recipient</th>
                    <th className="px-4 py-3">Tracking ID</th>
                  </tr>
                </thead>
                <tbody>
                  {recentMessages.map((msg) => (
                    <tr key={msg.tracking_id} className="border-t">
                      <td className="px-4 py-2 text-sm text-gray-500">{new Date(msg.created_at).toLocaleString()}</td>
                      <td className="px-4 py-2 text-sm">
                        <span className={`rounded px-2 py-1 capitalize ${
                          msg.status === 'delivered' ? 'bg-green-100 text-green-800' :
                          msg.status === 'failed' ? 'bg-red-100 text-red-800' :
                          'bg-gray-200'
                        }`}>{msg.status}</span>
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-500">{msg.recipient}</td>
                      <td className="px-4 py-2 text-sm text-blue-600">
                        <Link to={`/messages/${msg.tracking_id}`}>{msg.tracking_id}</Link>
                      </td>
                    </tr>
                  ))}
                  {recentMessages.length === 0 && !loading && (
                    <tr>
                      <td colSpan="4" className="px-4 py-2 text-center text-sm text-gray-500">
                        No recent messages.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default DashboardPage;