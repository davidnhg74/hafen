'use client';

import { useState } from 'react';

interface PrivilegeMapping {
  oracle_privilege: string;
  pg_equivalent: string | null;
  risk_level: number;
  recommendation: string;
  grant_sql: string | null;
}

interface UnmappablePrivilege {
  oracle_privilege: string;
  reason: string;
  workaround: string;
  risk_level: number;
}

interface PermissionAnalysisResponse {
  mappings: PrivilegeMapping[];
  unmappable: UnmappablePrivilege[];
  grant_sql: string[];
  overall_risk: string;
  analyzed_at: string;
}

interface PermissionAuditPanelProps {
  oracleConnectionId?: string;
  rawPrivilegesJson?: string;
  autoAnalyze?: boolean;
}

const riskColors = (level: number) => {
  if (level <= 3) return 'bg-green-50 border-green-200 text-green-700';
  if (level <= 6) return 'bg-yellow-50 border-yellow-200 text-yellow-700';
  return 'bg-red-50 border-red-200 text-red-700';
};

const riskBadgeColors = (level: number) => {
  if (level <= 3) return 'bg-green-100 text-green-800';
  if (level <= 6) return 'bg-yellow-100 text-yellow-800';
  return 'bg-red-100 text-red-800';
};

const overallRiskColors = {
  LOW: 'bg-green-50 border-green-200 text-green-700',
  MEDIUM: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  HIGH: 'bg-orange-50 border-orange-200 text-orange-700',
  CRITICAL: 'bg-red-50 border-red-200 text-red-700',
};

export default function PermissionAuditPanel({
  oracleConnectionId,
  rawPrivilegesJson,
  autoAnalyze = true,
}: PermissionAuditPanelProps) {
  const [loading, setLoading] = useState(autoAnalyze && !!rawPrivilegesJson);
  const [result, setResult] = useState<PermissionAnalysisResponse | null>(null);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const analyzePermissions = async () => {
    if (!oracleConnectionId && !rawPrivilegesJson) {
      setError('Either oracle_connection_id or oracle_privileges_json required');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/v3/analyze/permissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          oracle_connection_id: oracleConnectionId,
          oracle_privileges_json: rawPrivilegesJson,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to analyze permissions');
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const copyGrantSql = () => {
    if (result?.grant_sql) {
      const allSql = result.grant_sql.join('\n');
      navigator.clipboard.writeText(allSql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!result && !loading && !error && !autoAnalyze) {
    return null;
  }

  return (
    <div className="mt-8 space-y-4">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Permission Audit</h2>
        <p className="text-gray-600">
          Map Oracle privileges to PostgreSQL GRANT statements. Identifies unmappable privileges
          and risk levels for migration planning.
        </p>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center p-8 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="animate-spin h-5 w-5 text-blue-600 mr-3"></div>
          <p className="text-blue-700">Analyzing permissions...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-4">
          {/* Overall Risk Summary */}
          <div className={`border rounded-lg p-4 ${overallRiskColors[result.overall_risk as keyof typeof overallRiskColors]}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-gray-600 mb-1">Overall Risk Level</p>
                <p className="text-2xl font-bold">{result.overall_risk}</p>
              </div>
              <div className="text-right">
                <p className="text-xs font-medium text-gray-600 mb-1">Analyzed</p>
                <p className="text-sm font-mono">{new Date(result.analyzed_at).toLocaleString()}</p>
              </div>
            </div>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600 font-medium">Mapped Privileges</p>
              <p className="text-2xl font-bold text-gray-900">{result.mappings.length}</p>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600 font-medium">Unmappable</p>
              <p className="text-2xl font-bold text-orange-700">{result.unmappable.length}</p>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-600 font-medium">GRANT Statements</p>
              <p className="text-2xl font-bold text-blue-700">{result.grant_sql.length}</p>
            </div>
          </div>

          {/* GRANT SQL Copy Section */}
          {result.grant_sql.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">Generated GRANT Statements</h3>
                <button
                  onClick={copyGrantSql}
                  className={`px-3 py-1 rounded text-sm font-medium transition ${
                    copied
                      ? 'bg-green-100 text-green-700'
                      : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                  }`}
                >
                  {copied ? '✓ Copied' : 'Copy SQL'}
                </button>
              </div>
              <pre className="bg-gray-50 border border-gray-200 rounded p-3 text-xs overflow-x-auto max-h-40">
                {result.grant_sql.join('\n')}
              </pre>
            </div>
          )}

          {/* Mappings List */}
          {result.mappings.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm font-medium text-gray-700">
                {result.mappings.length} privilege{result.mappings.length !== 1 ? 's' : ''} mapped
              </p>
              {result.mappings.map((mapping, idx) => (
                <div
                  key={idx}
                  className={`border rounded-lg p-4 ${riskColors(mapping.risk_level)}`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <span className={`${riskBadgeColors(mapping.risk_level)} px-2 py-1 rounded text-xs font-semibold`}>
                      Risk: {mapping.risk_level}/10
                    </span>
                  </div>

                  <p className="font-mono text-sm font-bold text-gray-900 mb-3">
                    {mapping.oracle_privilege}
                  </p>

                  {mapping.pg_equivalent && (
                    <div className="mb-3">
                      <p className="text-xs text-gray-600 font-medium mb-1">PostgreSQL Equivalent</p>
                      <p className="font-mono text-sm bg-white bg-opacity-50 px-2 py-1 rounded">
                        {mapping.pg_equivalent}
                      </p>
                    </div>
                  )}

                  <div className="mb-3">
                    <p className="text-xs text-gray-600 font-medium mb-1">Recommendation</p>
                    <p className="text-sm text-gray-800">{mapping.recommendation}</p>
                  </div>

                  {mapping.grant_sql && (
                    <div>
                      <p className="text-xs text-gray-600 font-medium mb-1">GRANT Statement</p>
                      <p className="font-mono text-xs bg-white bg-opacity-50 px-2 py-1 rounded overflow-x-auto">
                        {mapping.grant_sql}
                      </p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Unmappable Privileges */}
          {result.unmappable.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm font-medium text-orange-700">
                {result.unmappable.length} unmappable privilege{result.unmappable.length !== 1 ? 's' : ''}
              </p>
              {result.unmappable.map((priv, idx) => (
                <div
                  key={idx}
                  className={`border rounded-lg p-4 ${riskColors(priv.risk_level)}`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <span className={`${riskBadgeColors(priv.risk_level)} px-2 py-1 rounded text-xs font-semibold`}>
                      Risk: {priv.risk_level}/10
                    </span>
                  </div>

                  <p className="font-mono text-sm font-bold text-gray-900 mb-3">
                    {priv.oracle_privilege}
                  </p>

                  <div className="mb-3">
                    <p className="text-xs text-gray-600 font-medium mb-1">Reason</p>
                    <p className="text-sm text-gray-800">{priv.reason}</p>
                  </div>

                  <div>
                    <p className="text-xs text-gray-600 font-medium mb-1">Workaround</p>
                    <p className="text-sm text-gray-800">{priv.workaround}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* No issues case */}
          {result.mappings.length === 0 && result.unmappable.length === 0 && (
            <div className="p-6 bg-green-50 border border-green-200 rounded-lg text-center">
              <p className="text-green-700 font-medium">✓ All privileges mapped successfully</p>
              <p className="text-green-600 text-sm mt-1">
                No unmappable privileges detected.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Manual Analyze Button */}
      {!autoAnalyze && (
        <button
          onClick={analyzePermissions}
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 px-4 rounded-lg font-medium transition"
        >
          {loading ? 'Analyzing...' : 'Analyze Permissions'}
        </button>
      )}
    </div>
  );
}
