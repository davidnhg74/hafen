'use client';

import { useState } from 'react';

interface CostAnalysis {
  oracle_breakdown: {
    license_cost_per_year: number;
    support_cost_per_year: number;
    infrastructure_cost_per_year: number;
    storage_cost_per_year: number;
    dba_salary_cost_per_year: number;
    total_annual_cost: number;
  };
  postgres_breakdown: {
    license_cost_per_year: number;
    support_cost_per_year: number;
    infrastructure_cost_per_year: number;
    storage_cost_per_year: number;
    dba_salary_cost_per_year: number;
    total_annual_cost: number;
  };
  annual_savings_year1: number;
  annual_savings_year2_plus: number;
  payback_months: number;
  roi_percent: number;
  five_year_savings: number;
}

export default function CostCalculator() {
  const [databaseSize, setDatabaseSize] = useState('medium');
  const [deploymentType, setDeploymentType] = useState('cloud_aws');
  const [numDatabases, setNumDatabases] = useState(1);
  const [numCores, setNumCores] = useState(4);
  const [numDbaFte, setNumDbaFte] = useState(1);

  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<CostAnalysis | null>(null);
  const [error, setError] = useState('');

  const handleCalculate = async () => {
    setLoading(true);
    setError('');

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/v3/cost-analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          database_size: databaseSize,
          deployment_type: deploymentType,
          num_databases: numDatabases,
          num_oracle_cores: numCores,
          num_dba_fte: numDbaFte,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to calculate costs');
      }

      const data = await response.json();
      setAnalysis(data.analysis);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
    }).format(value);
  };

  return (
    <div className="cost-calculator bg-white rounded-lg shadow-lg p-8">
      <h1 className="text-3xl font-bold mb-2 text-gray-900">Cost Savings Calculator</h1>
      <p className="text-gray-600 mb-8">
        See how much you'll save by migrating from Oracle to PostgreSQL
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* Database Size */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Database Size
          </label>
          <select
            value={databaseSize}
            onChange={(e) => setDatabaseSize(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
          >
            <option value="small">Small (&lt; 100 GB)</option>
            <option value="medium">Medium (100 GB - 1 TB)</option>
            <option value="large">Large (1 TB - 10 TB)</option>
            <option value="enterprise">Enterprise (&gt; 10 TB)</option>
          </select>
        </div>

        {/* Deployment Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Deployment Type
          </label>
          <select
            value={deploymentType}
            onChange={(e) => setDeploymentType(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
          >
            <option value="onprem">On-Premises</option>
            <option value="cloud_aws">Cloud (AWS)</option>
            <option value="cloud_azure">Cloud (Azure)</option>
            <option value="cloud_gcp">Cloud (GCP)</option>
          </select>
        </div>

        {/* Number of Databases */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Number of Databases
          </label>
          <input
            type="number"
            min="1"
            max="10"
            value={numDatabases}
            onChange={(e) => setNumDatabases(parseInt(e.target.value))}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
          />
        </div>

        {/* Oracle Cores */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Oracle CPU Cores
          </label>
          <input
            type="number"
            min="1"
            step="2"
            value={numCores}
            onChange={(e) => setNumCores(parseInt(e.target.value))}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
          />
        </div>

        {/* DBA FTE */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            DBA FTEs (Full-Time Equivalents)
          </label>
          <input
            type="number"
            min="0.5"
            step="0.5"
            value={numDbaFte}
            onChange={(e) => setNumDbaFte(parseFloat(e.target.value))}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
          />
        </div>
      </div>

      <button
        onClick={handleCalculate}
        disabled={loading}
        className="w-full bg-gradient-to-r from-purple-600 to-blue-600 text-white py-3 rounded-lg font-medium hover:from-purple-700 hover:to-blue-700 transition disabled:opacity-50"
      >
        {loading ? 'Calculating...' : 'Calculate Savings'}
      </button>

      {error && (
        <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {analysis && (
        <div className="mt-8 space-y-6">
          {/* ROI Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-gradient-to-br from-green-50 to-emerald-50 border-l-4 border-green-500 p-4 rounded">
              <p className="text-sm text-gray-600 font-medium">Annual Savings (Year 2+)</p>
              <p className="text-2xl font-bold text-green-700 mt-1">
                {formatCurrency(analysis.annual_savings_year2_plus)}
              </p>
            </div>

            <div className="bg-gradient-to-br from-blue-50 to-cyan-50 border-l-4 border-blue-500 p-4 rounded">
              <p className="text-sm text-gray-600 font-medium">Payback Period</p>
              <p className="text-2xl font-bold text-blue-700 mt-1">
                {analysis.payback_months.toFixed(1)} months
              </p>
            </div>

            <div className="bg-gradient-to-br from-purple-50 to-violet-50 border-l-4 border-purple-500 p-4 rounded">
              <p className="text-sm text-gray-600 font-medium">5-Year ROI</p>
              <p className="text-2xl font-bold text-purple-700 mt-1">
                {analysis.roi_percent.toFixed(0)}%
              </p>
            </div>

            <div className="bg-gradient-to-br from-orange-50 to-amber-50 border-l-4 border-orange-500 p-4 rounded">
              <p className="text-sm text-gray-600 font-medium">5-Year Savings</p>
              <p className="text-2xl font-bold text-orange-700 mt-1">
                {formatCurrency(analysis.five_year_savings)}
              </p>
            </div>
          </div>

          {/* Cost Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Oracle Costs */}
            <div className="border border-gray-200 rounded-lg p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Current Oracle Costs</h3>
              <div className="space-y-3">
                <div className="flex justify-between text-gray-700">
                  <span>Licenses:</span>
                  <span className="font-medium">
                    {formatCurrency(analysis.oracle_breakdown.license_cost_per_year)}
                  </span>
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>Support:</span>
                  <span className="font-medium">
                    {formatCurrency(analysis.oracle_breakdown.support_cost_per_year)}
                  </span>
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>Infrastructure:</span>
                  <span className="font-medium">
                    {formatCurrency(analysis.oracle_breakdown.infrastructure_cost_per_year)}
                  </span>
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>Storage:</span>
                  <span className="font-medium">
                    {formatCurrency(analysis.oracle_breakdown.storage_cost_per_year)}
                  </span>
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>DBA Salaries:</span>
                  <span className="font-medium">
                    {formatCurrency(analysis.oracle_breakdown.dba_salary_cost_per_year)}
                  </span>
                </div>
                <div className="border-t pt-3 flex justify-between text-gray-900 font-bold">
                  <span>Annual Total:</span>
                  <span>
                    {formatCurrency(analysis.oracle_breakdown.total_annual_cost)}
                  </span>
                </div>
              </div>
            </div>

            {/* PostgreSQL Costs */}
            <div className="border border-green-200 rounded-lg p-6 bg-green-50">
              <h3 className="text-lg font-bold text-gray-900 mb-4">PostgreSQL with Hafen</h3>
              <div className="space-y-3">
                <div className="flex justify-between text-gray-700">
                  <span>Licenses:</span>
                  <span className="font-medium">
                    {formatCurrency(analysis.postgres_breakdown.license_cost_per_year)}
                  </span>
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>Support:</span>
                  <span className="font-medium">
                    {formatCurrency(analysis.postgres_breakdown.support_cost_per_year)}
                  </span>
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>Infrastructure:</span>
                  <span className="font-medium">
                    {formatCurrency(analysis.postgres_breakdown.infrastructure_cost_per_year)}
                  </span>
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>Storage:</span>
                  <span className="font-medium">
                    {formatCurrency(analysis.postgres_breakdown.storage_cost_per_year)}
                  </span>
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>DBA Salaries:</span>
                  <span className="font-medium">
                    {formatCurrency(analysis.postgres_breakdown.dba_salary_cost_per_year)}
                  </span>
                </div>
                <div className="border-t border-green-300 pt-3 flex justify-between text-green-900 font-bold">
                  <span>Annual Total:</span>
                  <span>
                    {formatCurrency(analysis.postgres_breakdown.total_annual_cost)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Year 1 Summary */}
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Year 1 Projection</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600">Oracle Annual Cost</p>
                <p className="text-xl font-bold text-gray-900">
                  {formatCurrency(analysis.oracle_breakdown.total_annual_cost)}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">PostgreSQL Annual Cost</p>
                <p className="text-xl font-bold text-gray-900">
                  {formatCurrency(analysis.postgres_breakdown.total_annual_cost)}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Migration Investment</p>
                <p className="text-xl font-bold text-gray-900">-$25,000</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Net Year 1 Savings</p>
                <p className="text-xl font-bold text-green-700">
                  {formatCurrency(analysis.annual_savings_year1)}
                </p>
              </div>
            </div>
          </div>

          {/* Call to Action */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-2">Ready to save {formatCurrency(analysis.annual_savings_year2_plus)}/year?</h3>
            <p className="text-gray-600 mb-4">
              Let Hafen handle the migration. Your payback period is just {analysis.payback_months.toFixed(1)} months.
            </p>
            <a
              href="/convert"
              className="inline-block bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition font-medium"
            >
              Start Migration →
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
