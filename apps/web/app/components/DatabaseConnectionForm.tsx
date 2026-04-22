'use client';

import { useState } from 'react';
import { api } from '@/app/lib/api';

interface ConnectionDetails {
  host: string;
  port: number;
  username: string;
  password: string;
  database: string;
}

interface DatabaseConnectionFormProps {
  onAnalysisStart?: (jobId: string) => void;
}

export default function DatabaseConnectionForm({ onAnalysisStart }: DatabaseConnectionFormProps) {
  const [oracleConn, setOracleConn] = useState<ConnectionDetails>({
    host: '',
    port: 1521,
    username: '',
    password: '',
    database: '',
  });

  const [postgresConn, setPostgresConn] = useState<ConnectionDetails>({
    host: 'localhost',
    port: 5432,
    username: 'postgres',
    password: '',
    database: '',
  });

  const [activeTab, setActiveTab] = useState<'oracle' | 'postgres'>('oracle');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [testingConnection, setTestingConnection] = useState<'oracle' | 'postgres' | null>(null);

  const handleConnectionChange = (
    db: 'oracle' | 'postgres',
    field: keyof ConnectionDetails,
    value: string | number
  ) => {
    if (db === 'oracle') {
      setOracleConn({ ...oracleConn, [field]: value });
    } else {
      setPostgresConn({ ...postgresConn, [field]: value });
    }
  };

  const testConnection = async (db: 'oracle' | 'postgres') => {
    setTestingConnection(db);
    setError('');

    try {
      const conn = db === 'oracle' ? oracleConn : postgresConn;
      // Test connection endpoint would be on the backend
      // For now, just validate required fields
      if (!conn.host || !conn.username || !conn.password || !conn.database) {
        setError('Please fill in all connection details');
        return;
      }
      alert(`✓ ${db.toUpperCase()} connection validated`);
    } catch (err: any) {
      setError(err.message || `Failed to connect to ${db}`);
    } finally {
      setTestingConnection(null);
    }
  };

  const handleAnalyze = async () => {
    if (!oracleConn.host || !postgresConn.host) {
      setError('Please configure both Oracle and PostgreSQL connections');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await api.post('/api/v1/analyze', {
        oracle_connection: oracleConn,
        postgres_connection: postgresConn,
      });

      onAnalysisStart?.(response.data.job_id);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Analysis failed';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const ConnForm = ({ db, conn }: { db: 'oracle' | 'postgres'; conn: ConnectionDetails }) => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Host</label>
          <input
            type="text"
            value={conn.host}
            onChange={(e) => handleConnectionChange(db, 'host', e.target.value)}
            placeholder={db === 'oracle' ? 'oracle.example.com' : 'postgres.example.com'}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-purple-500 focus:border-purple-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Port</label>
          <input
            type="number"
            value={conn.port}
            onChange={(e) => handleConnectionChange(db, 'port', parseInt(e.target.value))}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-purple-500 focus:border-purple-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Username</label>
          <input
            type="text"
            value={conn.username}
            onChange={(e) => handleConnectionChange(db, 'username', e.target.value)}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-purple-500 focus:border-purple-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Password</label>
          <input
            type="password"
            value={conn.password}
            onChange={(e) => handleConnectionChange(db, 'password', e.target.value)}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-purple-500 focus:border-purple-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">Database/SID</label>
        <input
          type="text"
          value={conn.database}
          onChange={(e) => handleConnectionChange(db, 'database', e.target.value)}
          placeholder={db === 'oracle' ? 'ORCL' : 'postgres'}
          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-purple-500 focus:border-purple-500"
        />
      </div>

      <button
        onClick={() => testConnection(db)}
        disabled={testingConnection === db}
        className="w-full px-4 py-2 bg-gray-200 text-gray-900 font-medium rounded-md hover:bg-gray-300 disabled:bg-gray-100"
      >
        {testingConnection === db ? 'Testing...' : 'Test Connection'}
      </button>
    </div>
  );

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Database Configuration</h2>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-0 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('oracle')}
          className={`px-4 py-3 font-medium border-b-2 transition ${
            activeTab === 'oracle'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          }`}
        >
          Oracle Source
        </button>
        <button
          onClick={() => setActiveTab('postgres')}
          className={`px-4 py-3 font-medium border-b-2 transition ${
            activeTab === 'postgres'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          }`}
        >
          PostgreSQL Target
        </button>
      </div>

      {/* Forms */}
      <div className="mb-6">
        {activeTab === 'oracle' ? (
          <ConnForm db="oracle" conn={oracleConn} />
        ) : (
          <ConnForm db="postgres" conn={postgresConn} />
        )}
      </div>

      {/* Analyze Button */}
      <button
        onClick={handleAnalyze}
        disabled={loading}
        className="w-full px-6 py-3 bg-purple-600 text-white font-semibold rounded-md hover:bg-purple-700 disabled:bg-gray-400"
      >
        {loading ? 'Starting Analysis...' : 'Start Analysis'}
      </button>
    </div>
  );
}
