'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import AuthGuard from '../components/AuthGuard';

interface WorkflowData {
  id: string;
  name: string;
  migration_id: string | null;
  current_step: number;
  status: string;
  dba_notes: Record<string, any>;
  approvals: Record<string, any>;
  settings: Record<string, any>;
  created_at: string;
  updated_at: string;
}

const PHASES = [
  {
    name: 'ASSESSMENT',
    color: 'bg-blue-50 border-blue-200',
    steps: [
      { num: 1, name: 'Upload Schema', requiresApproval: false },
      { num: 2, name: 'Analyze Complexity', requiresApproval: false },
      { num: 3, name: 'DBA Review Scope', requiresApproval: true },
      { num: 4, name: 'Define Scope', requiresApproval: false },
    ],
  },
  {
    name: 'CONVERSION',
    color: 'bg-purple-50 border-purple-200',
    steps: [
      { num: 5, name: 'Auto-Convert Schema', requiresApproval: false },
      { num: 6, name: 'DBA Review Converted Code', requiresApproval: true },
      { num: 7, name: 'Refine Conversions', requiresApproval: false },
      { num: 8, name: 'DBA Review Test Plan', requiresApproval: true },
    ],
  },
  {
    name: 'MIGRATION PLANNING',
    color: 'bg-green-50 border-green-200',
    steps: [
      { num: 9, name: 'Capture Oracle Baseline', requiresApproval: false },
      { num: 10, name: 'DBA Review Migration Plan', requiresApproval: true },
      { num: 11, name: 'Prepare Target PostgreSQL', requiresApproval: false },
    ],
  },
  {
    name: 'EXECUTION',
    color: 'bg-orange-50 border-orange-200',
    steps: [
      { num: 12, name: 'Live Data Migration', requiresApproval: false },
      { num: 13, name: 'Handle Migration Errors', requiresApproval: false },
      { num: 14, name: 'Apply Post-Migration Scripts', requiresApproval: false },
      { num: 15, name: 'Capture PostgreSQL Metrics', requiresApproval: false },
    ],
  },
  {
    name: 'CUTOVER',
    color: 'bg-red-50 border-red-200',
    steps: [
      { num: 16, name: 'DBA Reviews Validation', requiresApproval: true },
      { num: 17, name: 'DBA Final Approval', requiresApproval: true },
      { num: 18, name: 'Switch Application', requiresApproval: false },
      { num: 19, name: 'Monitor Cutover', requiresApproval: false },
      { num: 20, name: 'Migration Complete', requiresApproval: false },
    ],
  },
];

const getStepStatus = (stepNum: number, currentStep: number, approvals: Record<string, any>, requiresApproval: boolean) => {
  if (stepNum < currentStep) {
    return approvals[stepNum] ? 'APPROVED' : 'COMPLETED';
  }
  if (stepNum === currentStep) {
    return requiresApproval ? 'NEEDS_DBA_REVIEW' : 'IN_PROGRESS';
  }
  return 'NOT_STARTED';
};

const getStatusColor = (status: string) => {
  switch (status) {
    case 'NOT_STARTED':
      return 'bg-gray-200 text-gray-800';
    case 'IN_PROGRESS':
      return 'bg-blue-200 text-blue-800 animate-pulse';
    case 'NEEDS_DBA_REVIEW':
      return 'bg-amber-200 text-amber-800';
    case 'APPROVED':
      return 'bg-green-200 text-green-800 border-2 border-green-500';
    case 'COMPLETED':
      return 'bg-green-500 text-white';
    case 'BLOCKED':
      return 'bg-red-200 text-red-800 border-2 border-red-500';
    case 'ERROR':
      return 'bg-red-500 text-white border-2 border-red-700';
    default:
      return 'bg-gray-200 text-gray-800';
  }
};

function MigrationCockpitPageContent() {
  const searchParams = useSearchParams();
  const workflowId = searchParams.get('workflow_id');

  const [workflow, setWorkflow] = useState<WorkflowData | null>(null);
  const [loading, setLoading] = useState(!!workflowId);
  const [error, setError] = useState('');
  const [approvalStep, setApprovalStep] = useState<number | null>(null);
  const [approvalNotes, setApprovalNotes] = useState('');
  const [approvingBy, setApprovingBy] = useState('');

  useEffect(() => {
    if (workflowId) {
      fetchWorkflow();
    }
  }, [workflowId]);

  const fetchWorkflow = async () => {
    if (!workflowId) return;

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/v3/workflow/${workflowId}`);

      if (!response.ok) {
        throw new Error('Failed to fetch workflow');
      }

      const data = await response.json();
      setWorkflow(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!workflow || approvalStep === null || !approvingBy.trim()) {
      return;
    }

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/v3/workflow/${workflow.id}/approve/${approvalStep}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved_by: approvingBy,
          notes: approvalNotes,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to approve step');
      }

      const updated = await response.json();
      setWorkflow(updated);
      setApprovalStep(null);
      setApprovalNotes('');
      setApprovingBy('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin h-12 w-12 text-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-700">Loading migration workflow...</p>
        </div>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">Migration Cockpit</h1>
          <p className="text-gray-600 mb-4">Provide a workflow_id parameter to view migration progress.</p>
          <p className="text-gray-500 text-sm">Example: /migration?workflow_id=...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">{workflow.name}</h1>
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <span>Phase: {Math.ceil(workflow.current_step / 4)} of 5</span>
            <span>Step: {workflow.current_step} of 20</span>
            <span>Status: <span className="font-semibold text-gray-900">{workflow.status.toUpperCase()}</span></span>
            <div className="ml-auto">
              <div className="bg-white rounded-lg px-4 py-2 border border-gray-200">
                <div className="text-xs text-gray-600">Progress</div>
                <div className="text-2xl font-bold text-gray-900">{Math.round((workflow.current_step / 20) * 100)}%</div>
              </div>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {/* Timeline */}
        <div className="space-y-8">
          {PHASES.map((phase, phaseIdx) => (
            <div key={phaseIdx} className={`border rounded-lg p-6 ${phase.color}`}>
              <h2 className="text-lg font-bold text-gray-900 mb-6">PHASE {phaseIdx + 1}: {phase.name}</h2>

              <div className="space-y-4">
                {phase.steps.map((step, stepIdx) => {
                  const status = getStepStatus(step.num, workflow.current_step, workflow.approvals, step.requiresApproval);
                  const isCurrentStep = step.num === workflow.current_step;
                  const statusColor = getStatusColor(status);

                  return (
                    <div key={stepIdx} className="flex items-start gap-4">
                      {/* Timeline dot */}
                      <div className="flex flex-col items-center pt-1">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${statusColor}`}>
                          {step.num}
                        </div>
                        {stepIdx < phase.steps.length - 1 && (
                          <div className="w-0.5 h-12 bg-gray-300 my-2"></div>
                        )}
                      </div>

                      {/* Step content */}
                      <div className="flex-1 pt-1">
                        <div className="flex items-center gap-2 mb-2">
                          <h3 className="font-semibold text-gray-900">{step.name}</h3>
                          {step.requiresApproval && (
                            <span className="px-2 py-1 bg-amber-100 text-amber-800 text-xs font-semibold rounded">
                              DBA APPROVAL
                            </span>
                          )}
                          {status === 'NEEDS_DBA_REVIEW' && (
                            <span className="px-2 py-1 bg-red-100 text-red-800 text-xs font-semibold rounded animate-pulse">
                              WAITING
                            </span>
                          )}
                        </div>

                        {status === 'NEEDS_DBA_REVIEW' && (
                          <div className="mt-3 p-4 bg-white rounded-lg border border-amber-200">
                            <button
                              onClick={() => setApprovalStep(step.num)}
                              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded font-medium transition"
                            >
                              Approve Step {step.num}
                            </button>
                          </div>
                        )}

                        {workflow.approvals[step.num] && (
                          <div className="mt-2 text-xs text-green-700 bg-white bg-opacity-50 px-2 py-1 rounded">
                            ✓ Approved by {workflow.approvals[step.num].approved_by}
                            {workflow.approvals[step.num].notes && (
                              <p className="mt-1 text-gray-700">{workflow.approvals[step.num].notes}</p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Approval Modal */}
        {approvalStep !== null && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-lg max-w-md w-full p-6">
              <h3 className="text-xl font-bold text-gray-900 mb-4">
                Approve Step {approvalStep}
              </h3>

              <div className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    DBA Name
                  </label>
                  <input
                    type="text"
                    value={approvingBy}
                    onChange={(e) => setApprovingBy(e.target.value)}
                    placeholder="e.g., John Smith"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Notes (optional)
                  </label>
                  <textarea
                    value={approvalNotes}
                    onChange={(e) => setApprovalNotes(e.target.value)}
                    placeholder="Any approval notes or conditions..."
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setApprovalStep(null)}
                  className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-900 rounded-lg font-medium transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleApprove}
                  disabled={!approvingBy.trim()}
                  className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg font-medium transition"
                >
                  Approve
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function MigrationCockpitPage() {
  return (
    <AuthGuard>
      <MigrationCockpitPageContent />
    </AuthGuard>
  );
}
