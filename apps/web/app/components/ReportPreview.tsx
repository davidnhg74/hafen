'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';

interface JobResponse {
  id: string;
  status: string;
  complexity_report?: {
    score: number;
    total_lines: number;
    auto_convertible_lines: number;
    needs_review_lines: number;
    must_rewrite_lines: number;
    construct_counts: { [key: string]: number };
    effort_estimate_days: number;
    estimated_cost: number;
    top_10_constructs: string[];
  };
  created_at: string;
  completed_at?: string;
  error_message?: string;
}

interface ReportPreviewProps {
  jobId: string;
  onBack: () => void;
}

export default function ReportPreview({ jobId, onBack }: ReportPreviewProps) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [pollCount, setPollCount] = useState(0);

  useEffect(() => {
    const fetchJob = async () => {
      try {
        const response = await axios.get(
          `${process.env.NEXT_PUBLIC_API_URL}/api/v1/jobs/${jobId}`
        );
        setJob(response.data);

        if (response.data.status === 'done' || response.data.status === 'error') {
          setIsLoading(false);
        }
      } catch (error) {
        console.error('Error fetching job:', error);
      }
    };

    fetchJob();

    if (isLoading && pollCount < 60) {
      const timer = setTimeout(() => {
        setPollCount(pollCount + 1);
      }, 2000);

      return () => clearTimeout(timer);
    }
  }, [jobId, isLoading, pollCount]);

  if (isLoading || !job) {
    return (
      <div className="w-full max-w-2xl mx-auto text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
        <p className="mt-4 text-lg font-medium text-gray-900">Analyzing your PL/SQL...</p>
        <p className="text-sm text-gray-500 mt-2">This may take a minute</p>
      </div>
    );
  }

  if (job.status === 'error') {
    return (
      <div className="w-full max-w-2xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h2 className="text-lg font-bold text-red-900 mb-2">Analysis Failed</h2>
          <p className="text-red-700">{job.error_message || 'An unknown error occurred'}</p>
          <button
            onClick={onBack}
            className="mt-4 bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const report = job.complexity_report;
  if (!report) {
    return null;
  }

  const scoreColor =
    report.score < 30
      ? 'score-low'
      : report.score < 60
      ? 'score-medium'
      : 'score-high';

  const totalClassified =
    report.auto_convertible_lines +
    report.needs_review_lines +
    report.must_rewrite_lines;

  const autoPct =
    totalClassified > 0
      ? ((report.auto_convertible_lines / totalClassified) * 100).toFixed(1)
      : 0;
  const reviewPct =
    totalClassified > 0
      ? ((report.needs_review_lines / totalClassified) * 100).toFixed(1)
      : 0;
  const rewritePct =
    totalClassified > 0
      ? ((report.must_rewrite_lines / totalClassified) * 100).toFixed(1)
      : 0;

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6">
      {/* Score Card */}
      <div className="bg-white rounded-lg shadow-lg p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8 text-center">
          Complexity Analysis Report
        </h1>

        <div className="flex flex-col items-center mb-8">
          <div className={`score-badge ${scoreColor}`}>{report.score}</div>
          <p className="mt-4 text-sm text-gray-600 text-center">
            {report.score < 30
              ? 'Low Complexity'
              : report.score < 60
              ? 'Moderate Complexity'
              : 'High Complexity'}
          </p>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="bg-gray-50 p-4 rounded-lg">
            <p className="text-sm text-gray-600">Total Lines</p>
            <p className="text-2xl font-bold text-gray-900">{report.total_lines}</p>
          </div>
          <div className="bg-gray-50 p-4 rounded-lg">
            <p className="text-sm text-gray-600">Estimated Effort</p>
            <p className="text-2xl font-bold text-gray-900">
              {report.effort_estimate_days} days
            </p>
          </div>
          <div className="bg-gray-50 p-4 rounded-lg">
            <p className="text-sm text-gray-600">Estimated Cost</p>
            <p className="text-2xl font-bold text-gray-900">
              ${Math.round(report.estimated_cost).toLocaleString()}
            </p>
          </div>
          <div className="bg-gray-50 p-4 rounded-lg">
            <p className="text-sm text-gray-600">Found Constructs</p>
            <p className="text-2xl font-bold text-gray-900">
              {Object.values(report.construct_counts).reduce((a, b) => a + b, 0)}
            </p>
          </div>
        </div>

        {/* Line Breakdown */}
        <div className="mb-8">
          <h3 className="font-bold text-gray-900 mb-4">Line Classification</h3>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-700">Auto-convertible</span>
                <span className="font-medium">{autoPct}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-green-500 h-2 rounded-full"
                  style={{ width: `${autoPct}%` }}
                ></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-700">Needs Review</span>
                <span className="font-medium">{reviewPct}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-yellow-500 h-2 rounded-full"
                  style={{ width: `${reviewPct}%` }}
                ></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-700">Must Rewrite</span>
                <span className="font-medium">{rewritePct}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-red-500 h-2 rounded-full"
                  style={{ width: `${rewritePct}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>

        {/* Top Constructs */}
        {report.top_10_constructs.length > 0 && (
          <div className="mb-8">
            <h3 className="font-bold text-gray-900 mb-3">Top Constructs</h3>
            <div className="bg-gray-50 p-4 rounded-lg">
              <ul className="space-y-2 text-sm">
                {report.top_10_constructs.slice(0, 10).map((construct, idx) => (
                  <li key={idx} className="text-gray-700">
                    • {construct}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* CTA */}
        <div className="border-t pt-6 mt-6">
          <button
            onClick={onBack}
            className="w-full bg-gray-200 text-gray-900 px-6 py-3 rounded-lg hover:bg-gray-300 transition font-medium mb-3"
          >
            ← Back
          </button>
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL}/api/v1/report/${jobId}/pdf`}
            download={`depart_analysis_${jobId}.pdf`}
            className="block w-full bg-purple-600 text-white px-6 py-3 rounded-lg hover:bg-purple-700 transition font-medium text-center"
          >
            Download Full PDF Report
          </a>
        </div>
      </div>
    </div>
  );
}
