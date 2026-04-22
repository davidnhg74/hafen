'use client';

import { useState } from 'react';
import UploadZone from './components/UploadZone';
import ReportPreview from './components/ReportPreview';

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string>('');

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50">
      {/* Header */}
      <header className="gradient-bg text-white py-16">
        <div className="container mx-auto px-4 text-center">
          <p className="text-xl text-purple-100">
            Escape Oracle Licensing with AI-Powered PL/SQL to PostgreSQL Migration
          </p>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-16">
        {jobId ? (
          <ReportPreview jobId={jobId} onBack={() => setJobId(null)} />
        ) : (
          <div className="space-y-8">
            {/* Error Alert */}
            {error && (
              <div className="w-full max-w-2xl mx-auto bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-red-700 font-medium">{error}</p>
                <button
                  onClick={() => setError('')}
                  className="text-red-500 hover:text-red-700 text-sm mt-2"
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Instructions */}
            <div className="w-full max-w-2xl mx-auto bg-white rounded-lg shadow-sm p-6 border border-gray-100">
              <h2 className="text-xl font-bold text-gray-900 mb-4">How It Works</h2>
              <ol className="space-y-3 text-gray-700">
                <li className="flex gap-3">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-purple-100 text-purple-700 font-bold text-sm">
                    1
                  </span>
                  <span>Upload a zip file containing your Oracle DDL and PL/SQL code</span>
                </li>
                <li className="flex gap-3">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-purple-100 text-purple-700 font-bold text-sm">
                    2
                  </span>
                  <span>
                    Our analyzer scans for complex constructs (CONNECT BY, MERGE, DBMS_*, etc.)
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-purple-100 text-purple-700 font-bold text-sm">
                    3
                  </span>
                  <span>
                    Get a detailed PDF report with complexity score, effort estimate, and cost
                  </span>
                </li>
              </ol>
            </div>

            {/* Phase 1: Upload Zone */}
            <UploadZone
              onUploadStart={(id) => setJobId(id)}
              onUploadError={(err) => setError(err)}
            />

            {/* Phase 2: Converter CTA */}
            <div className="w-full max-w-2xl mx-auto bg-white rounded-lg shadow-sm p-6 border border-gray-100">
              <h2 className="text-xl font-bold text-gray-900 mb-2">Ready to convert?</h2>
              <p className="text-gray-700 mb-4">
                Try our interactive PL/SQL converter to transform your Oracle code to PostgreSQL in real-time.
              </p>
              <a
                href="/convert"
                className="inline-block bg-gradient-to-r from-purple-600 to-blue-600 text-white px-6 py-3 rounded-lg hover:from-purple-700 hover:to-blue-700 transition font-medium"
              >
                Open Converter →
              </a>
            </div>

            {/* Phase 3: ROI Calculator CTA */}
            <div className="w-full max-w-2xl mx-auto bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg shadow-sm p-6 border border-green-200">
              <h2 className="text-xl font-bold text-gray-900 mb-2">Need to justify the migration?</h2>
              <p className="text-gray-700 mb-4">
                Use our ROI calculator to show your CFO exactly how much you'll save by migrating from Oracle to PostgreSQL.
              </p>
              <a
                href="/pricing"
                className="inline-block bg-gradient-to-r from-green-600 to-emerald-600 text-white px-6 py-3 rounded-lg hover:from-green-700 hover:to-emerald-700 transition font-medium"
              >
                Calculate ROI →
              </a>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12 mt-16">
        <div className="container mx-auto px-4 text-center">
          <p className="mb-2">© 2024 Depart. All rights reserved.</p>
          <p className="text-sm">
            Built by Oracle DBAs, for teams migrating off Oracle to PostgreSQL
          </p>
        </div>
      </footer>
    </div>
  );
}
