'use client';

interface AnalysisJob {
  id: string;
  status: string;
  created_at: string;
  completed_at?: string;
  rate_per_day?: number;
}

interface RecentJobsTableProps {
  jobs: AnalysisJob[];
}

export default function RecentJobsTable({ jobs }: RecentJobsTableProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-50 text-green-700';
      case 'pending':
        return 'bg-yellow-50 text-yellow-700';
      case 'processing':
        return 'bg-blue-50 text-blue-700';
      case 'failed':
        return 'bg-red-50 text-red-700';
      default:
        return 'bg-gray-50 text-gray-700';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (jobs.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No migration jobs yet. <a href="/migration" className="text-purple-600 hover:text-purple-700 font-medium">Start a migration</a>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-3 px-4 font-semibold text-gray-700">Job ID</th>
            <th className="text-left py-3 px-4 font-semibold text-gray-700">Status</th>
            <th className="text-left py-3 px-4 font-semibold text-gray-700">Created</th>
            <th className="text-left py-3 px-4 font-semibold text-gray-700">Completed</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} className="border-b border-gray-100 hover:bg-gray-50">
              <td className="py-3 px-4 text-sm text-gray-900 font-mono">{job.id.slice(0, 8)}</td>
              <td className="py-3 px-4">
                <span className={`text-xs font-semibold py-1 px-2 rounded capitalize ${getStatusColor(job.status)}`}>
                  {job.status}
                </span>
              </td>
              <td className="py-3 px-4 text-sm text-gray-600">{formatDate(job.created_at)}</td>
              <td className="py-3 px-4 text-sm text-gray-600">
                {job.completed_at ? formatDate(job.completed_at) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
