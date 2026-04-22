'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import AuthGuard from '@/app/components/AuthGuard';
import { api } from '@/app/lib/api';

function TicketDetailContent() {
  const params = useParams();
  const ticketId = params.id as string;

  const [ticket, setTicket] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadTicket();
  }, [ticketId]);

  const loadTicket = async () => {
    try {
      const response = await api.get(`/api/v4/support/tickets/${ticketId}`);
      setTicket(response.data.ticket);
      setMessages(response.data.messages || []);
    } catch (err) {
      setError('Failed to load ticket');
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMessage.trim()) return;

    setLoading(true);
    setError('');

    try {
      await api.post(`/api/v4/support/tickets/${ticketId}/messages`, {
        body: newMessage,
      });
      setNewMessage('');
      await loadTicket();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to send message');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (newStatus: string) => {
    try {
      await api.put(`/api/v4/support/tickets/${ticketId}/status`, {
        status: newStatus,
      });
      await loadTicket();
    } catch (err) {
      setError('Failed to update status');
    }
  };

  if (!ticket) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <p className="text-gray-600">Loading...</p>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'closed':
        return 'bg-gray-100 text-gray-700';
      case 'resolved':
        return 'bg-green-100 text-green-700';
      case 'in_progress':
        return 'bg-blue-100 text-blue-700';
      case 'open':
        return 'bg-yellow-100 text-yellow-700';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-8">
      <Link href="/support" className="text-purple-600 hover:text-purple-700 font-medium mb-6 inline-block">
        ← Back to tickets
      </Link>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{ticket.subject}</h1>
            <p className="text-sm text-gray-600 mt-1">
              Created {new Date(ticket.created_at).toLocaleDateString()}
            </p>
          </div>
          <span
            className={`inline-block px-3 py-1 rounded-full text-sm font-semibold capitalize ${getStatusColor(
              ticket.status
            )}`}
          >
            {ticket.status.replace('_', ' ')}
          </span>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Status Actions */}
        {ticket.status !== 'closed' && (
          <div className="flex gap-2 mb-6">
            {ticket.status !== 'resolved' && (
              <button
                onClick={() => handleUpdateStatus('resolved')}
                className="px-4 py-2 bg-green-600 text-white font-medium rounded-md hover:bg-green-700 text-sm"
              >
                Mark as Resolved
              </button>
            )}
            <button
              onClick={() => handleUpdateStatus('closed')}
              className="px-4 py-2 bg-gray-600 text-white font-medium rounded-md hover:bg-gray-700 text-sm"
            >
              Close Ticket
            </button>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="space-y-4 mb-6">
        {messages.map((msg) => (
          <div key={msg.id} className={`rounded-lg p-4 ${msg.is_staff ? 'bg-blue-50' : 'bg-gray-50'}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="font-semibold text-gray-900">
                {msg.is_staff ? 'Support Team' : msg.author?.email || 'You'}
              </span>
              {msg.is_staff && <span className="text-xs bg-blue-200 text-blue-800 px-2 py-1 rounded">Staff</span>}
              <span className="text-xs text-gray-600">
                {new Date(msg.created_at).toLocaleDateString()} {new Date(msg.created_at).toLocaleTimeString()}
              </span>
            </div>
            <p className="text-gray-700 whitespace-pre-wrap">{msg.body}</p>
          </div>
        ))}
      </div>

      {/* Reply Form */}
      {ticket.status !== 'closed' && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Add a Reply</h2>
          <form onSubmit={handleSendMessage} className="space-y-4">
            <textarea
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              rows={4}
              placeholder="Type your reply..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-purple-500 focus:border-purple-500"
            />
            <button
              type="submit"
              disabled={loading || !newMessage.trim()}
              className="px-6 py-2 bg-purple-600 text-white font-medium rounded-md hover:bg-purple-700 disabled:bg-gray-400"
            >
              {loading ? 'Sending...' : 'Send Reply'}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

export default function TicketDetailPage() {
  return (
    <AuthGuard>
      <TicketDetailContent />
    </AuthGuard>
  );
}
