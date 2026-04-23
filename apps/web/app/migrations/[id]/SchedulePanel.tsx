'use client';

/**
 * Schedule card on the migration detail page.
 *
 * Shows the current cron expression + timezone + next fire + last run
 * summary, with an inline editor for admins. The card gracefully
 * handles three states:
 *
 *  - License missing: renders a subdued upsell pointing at /settings/instance
 *  - No schedule yet: renders a "Set up a schedule" CTA
 *  - Schedule configured: shows current state + Edit / Delete / Run now
 */

import { useEffect, useState } from 'react';
import Link from 'next/link';

import {
  MigrationScheduleView,
  deleteSchedule,
  getSchedule,
  scheduleRunNow,
  upsertSchedule,
} from '@/app/lib/api';
import { useAuthStore } from '@/app/store/authStore';


type LoadState =
  | { kind: 'loading' }
  | { kind: 'ok'; schedule: MigrationScheduleView | null }
  | { kind: 'unlicensed' }
  | { kind: 'error'; message: string };


export default function SchedulePanel({ migrationId }: { migrationId: string }) {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'admin';
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const [editing, setEditing] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  async function refresh() {
    setState({ kind: 'loading' });
    try {
      const schedule = await getSchedule(migrationId);
      setState({ kind: 'ok', schedule });
    } catch (e: any) {
      if (e?.response?.status === 402) {
        setState({ kind: 'unlicensed' });
        return;
      }
      setState({
        kind: 'error',
        message: e?.response?.data?.detail || e?.message || 'Failed to load.',
      });
    }
  }

  useEffect(() => {
    void refresh();
  }, [migrationId]);

  async function doRunNow() {
    setFlash(null);
    try {
      const r = await scheduleRunNow(migrationId);
      setFlash(`Clone enqueued as migration ${r.migration_id.slice(0, 8)}…`);
      await refresh();
    } catch (e: any) {
      setFlash(e?.response?.data?.detail || e?.message || 'Run-now failed.');
    }
  }

  async function doDelete() {
    if (!window.confirm('Delete this schedule? Future runs will stop.')) return;
    try {
      await deleteSchedule(migrationId);
      await refresh();
    } catch (e: any) {
      setFlash(e?.response?.data?.detail || e?.message || 'Delete failed.');
    }
  }

  return (
    <section className="mt-6 rounded-xl border border-gray-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Schedule</h2>
        {state.kind === 'ok' && isAdmin && !editing && (
          <div className="flex gap-2">
            {state.schedule && (
              <>
                <button
                  onClick={doRunNow}
                  className="rounded border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  Run now
                </button>
                <button
                  onClick={() => setEditing(true)}
                  className="rounded border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  Edit
                </button>
                <button
                  onClick={doDelete}
                  className="rounded border border-red-300 bg-white px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
                >
                  Delete
                </button>
              </>
            )}
            {!state.schedule && (
              <button
                onClick={() => setEditing(true)}
                className="rounded-lg bg-purple-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-purple-700"
              >
                Set up schedule
              </button>
            )}
          </div>
        )}
      </div>

      {state.kind === 'loading' && (
        <p className="mt-3 text-sm text-gray-500">Loading…</p>
      )}

      {state.kind === 'unlicensed' && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          Recurring migrations require a Pro license with the{' '}
          <code className="rounded bg-amber-100 px-1">scheduled_migrations</code>{' '}
          feature.{' '}
          <Link href="/settings/instance" className="underline">
            Manage license →
          </Link>
        </div>
      )}

      {state.kind === 'error' && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {state.message}
        </div>
      )}

      {state.kind === 'ok' && !state.schedule && !editing && (
        <p className="mt-3 text-sm text-gray-600">
          Run this migration on a cron cadence. Each fire clones the
          current config into a new run — history stays intact.
        </p>
      )}

      {state.kind === 'ok' && state.schedule && !editing && (
        <ScheduleSummary schedule={state.schedule} />
      )}

      {editing && (
        <ScheduleEditor
          migrationId={migrationId}
          existing={state.kind === 'ok' ? state.schedule : null}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            void refresh();
          }}
        />
      )}

      {flash && (
        <p className="mt-3 text-sm text-gray-700">{flash}</p>
      )}
    </section>
  );
}


function ScheduleSummary({ schedule }: { schedule: MigrationScheduleView }) {
  return (
    <div className="mt-3 grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
      <Field label="Cron">
        <code className="rounded bg-gray-100 px-1.5 py-0.5 font-mono">
          {schedule.cron_expr}
        </code>
        <span className="ml-2 text-gray-500">({schedule.timezone})</span>
      </Field>
      <Field label="Status">
        {schedule.enabled ? (
          <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
            enabled
          </span>
        ) : (
          <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700">
            disabled
          </span>
        )}
      </Field>
      <Field label="Next run">
        {schedule.next_run_at
          ? new Date(schedule.next_run_at).toLocaleString()
          : '—'}
      </Field>
      <Field label="Last run">
        {schedule.last_run_at
          ? `${new Date(schedule.last_run_at).toLocaleString()} · ${schedule.last_run_status || 'no status'}`
          : 'Never fired'}
      </Field>
    </div>
  );
}


function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-0.5">{children}</div>
    </div>
  );
}


function ScheduleEditor({
  migrationId,
  existing,
  onCancel,
  onSaved,
}: {
  migrationId: string;
  existing: MigrationScheduleView | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(existing?.name || 'Scheduled run');
  const [cron, setCron] = useState(existing?.cron_expr || '0 2 * * *');
  const [tz, setTz] = useState(existing?.timezone || 'UTC');
  const [enabled, setEnabled] = useState(existing?.enabled ?? true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      await upsertSchedule(migrationId, {
        name,
        cron_expr: cron,
        timezone: tz,
        enabled,
      });
      onSaved();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setErr(typeof detail === 'string' ? detail : e?.message || 'Save failed.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-4 space-y-3">
      <label className="block">
        <span className="text-sm font-medium text-gray-700">Name</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
      </label>
      <label className="block">
        <span className="text-sm font-medium text-gray-700">
          Cron expression (5 fields)
        </span>
        <input
          value={cron}
          onChange={(e) => setCron(e.target.value)}
          placeholder="0 2 * * *"
          className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm"
        />
        <span className="mt-1 block text-xs text-gray-500">
          Examples: <code className="font-mono">0 2 * * *</code> (2am daily),{' '}
          <code className="font-mono">*/15 * * * *</code> (every 15 min),{' '}
          <code className="font-mono">0 */6 * * 1-5</code> (every 6h, weekdays).
        </span>
      </label>
      <label className="block">
        <span className="text-sm font-medium text-gray-700">Timezone (IANA)</span>
        <input
          value={tz}
          onChange={(e) => setTz(e.target.value)}
          placeholder="UTC or America/New_York"
          className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm"
        />
      </label>
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        Enabled (fires at the next scheduled time when checked)
      </label>
      {err && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {err}
        </div>
      )}
      <div className="flex gap-3 pt-1">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : existing ? 'Save changes' : 'Create schedule'}
        </button>
        <button
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
