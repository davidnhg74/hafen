/**
 * Public log troubleshooter — paste or upload, get an AI diagnosis.
 *
 * The first AI feature on hafen.ai accessible to anonymous visitors.
 * Doubles as a marketing demo: a stuck DBA hits the page at 2am,
 * pastes their error, gets a useful answer in seconds. No signup
 * required for the first 3 analyses/day.
 *
 * Two input tabs that hit the same backend service:
 *   - Paste: large textarea
 *   - Upload: drag-drop / file picker, multi-file (≤5), .gz aware
 *
 * Honest cost coaching surfaces under the input — focused logs
 * produce sharper diagnoses (prompt is truncated to ~50KB regardless
 * of upload size, so trimming is more about quality than tokens).
 */
'use client';

import { useState } from 'react';

import {
  analyzeLogsPaste,
  analyzeLogsUpload,
  type Diagnosis,
} from '@/app/lib/api';


type Tab = 'paste' | 'upload';

const SAMPLE_LOG = `ORA-01017: invalid username/password; logon denied
SQL*Plus: Release 23.0.0.0.0
ERROR at line 1:
ORA-12545: Connect failed because target host or object does not exist`;

const TRIM_HINTS = [
  { cmd: 'tail -2000 alert.log', note: 'last 2000 lines' },
  { cmd: "grep -B 5 -A 20 'ORA-' migration.log", note: '5 lines before, 20 after each error' },
  { cmd: "awk '/ERROR/,/COMMIT/' runner.log", note: 'ERROR through next COMMIT' },
];


export default function TroubleshootPage() {
  const [tab, setTab] = useState<Tab>('paste');
  const [logs, setLogs] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [context, setContext] = useState('');
  const [stage, setStage] = useState('');
  const [showTrimHints, setShowTrimHints] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);

  const totalFileBytes = files.reduce((acc, f) => acc + f.size, 0);
  const showLargeFileNote = totalFileBytes > 10 * 1024 * 1024;

  async function submit() {
    setError(null);
    setDiagnosis(null);
    setLoading(true);
    try {
      const result =
        tab === 'paste'
          ? await analyzeLogsPaste({
              logs,
              context: context || undefined,
              stage: stage || undefined,
            })
          : await analyzeLogsUpload(files, context || undefined, stage || undefined);
      setDiagnosis(result);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Analysis failed. Please retry.');
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = tab === 'paste' ? logs.trim().length > 0 : files.length > 0;

  return (
    <div className="container mx-auto px-4 py-12 max-w-4xl">
      <h1 className="text-4xl font-bold text-gray-900 mb-2">
        Stuck on an Oracle migration?
      </h1>
      <p className="text-lg text-gray-600 mb-8">
        Paste your error or drop a log file. We&apos;ll diagnose what&apos;s wrong
        and suggest the next step — usually in 5 seconds.
      </p>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6">
        <TabButton active={tab === 'paste'} onClick={() => setTab('paste')}>
          Paste
        </TabButton>
        <TabButton active={tab === 'upload'} onClick={() => setTab('upload')}>
          Upload files
        </TabButton>
      </div>

      {/* Coaching banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-4 text-sm text-blue-900">
        <p>
          <strong>Tip:</strong> paste only the error section + a few lines of
          context for best results. We smart-truncate larger logs anyway, but a
          focused log produces a sharper diagnosis.
        </p>
        <button
          type="button"
          className="mt-2 underline text-blue-700 hover:text-blue-900"
          onClick={() => setShowTrimHints(!showTrimHints)}
        >
          {showTrimHints ? 'Hide' : 'Show'} how to trim
        </button>
        {showTrimHints && (
          <div className="mt-3 space-y-2">
            {TRIM_HINTS.map((h) => (
              <div key={h.cmd} className="font-mono text-xs bg-white border border-blue-200 rounded p-2">
                <span className="text-blue-700">$</span> {h.cmd}
                <span className="text-gray-500 ml-3 font-sans">— {h.note}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Input area */}
      {tab === 'paste' ? (
        <textarea
          value={logs}
          onChange={(e) => setLogs(e.target.value)}
          placeholder={SAMPLE_LOG}
          rows={14}
          className="w-full font-mono text-sm border border-gray-300 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-purple-500 mb-2"
          disabled={loading}
        />
      ) : (
        <FileDropZone
          files={files}
          onChange={setFiles}
          disabled={loading}
        />
      )}

      {showLargeFileNote && (
        <p className="text-xs text-gray-600 mb-3">
          This is a large upload ({(totalFileBytes / 1024 / 1024).toFixed(1)} MB).
          We&apos;ll extract relevant error windows; trimming yourself usually
          produces a sharper diagnosis.
        </p>
      )}

      {/* Sample button + stage dropdown */}
      <div className="flex flex-wrap gap-3 mb-6 items-center">
        {tab === 'paste' && (
          <button
            type="button"
            onClick={() => setLogs(SAMPLE_LOG)}
            className="text-sm text-purple-700 hover:text-purple-900 underline"
            disabled={loading}
          >
            Try a sample
          </button>
        )}
        <select
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          className="text-sm border border-gray-300 rounded-md px-2 py-1"
          disabled={loading}
        >
          <option value="">Stage (optional)</option>
          <option value="ddl">DDL</option>
          <option value="data_load">Data load</option>
          <option value="verify">Verify</option>
          <option value="cutover">Cutover</option>
        </select>
      </div>

      <button
        type="button"
        onClick={submit}
        disabled={!canSubmit || loading}
        className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 text-white font-semibold px-6 py-2 rounded-md"
      >
        {loading ? 'Analyzing…' : 'Diagnose'}
      </button>

      {/* Privacy note */}
      <p className="text-xs text-gray-500 mt-3">
        Logs are sent to Anthropic Claude for analysis and stored in our audit
        log as confidential. Don&apos;t paste secrets or PII.
      </p>

      {/* Error display */}
      {error && (
        <div className="mt-6 bg-red-50 border border-red-200 rounded-md p-4 text-red-900 text-sm">
          {error}
        </div>
      )}

      {/* Diagnosis panel */}
      {diagnosis && <DiagnosisPanel diagnosis={diagnosis} />}
    </div>
  );
}


function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'px-4 py-2 font-medium text-sm border-b-2 transition-colors ' +
        (active
          ? 'border-purple-600 text-purple-700'
          : 'border-transparent text-gray-500 hover:text-gray-700')
      }
    >
      {children}
    </button>
  );
}


function FileDropZone({
  files,
  onChange,
  disabled,
}: {
  files: File[];
  onChange: (files: File[]) => void;
  disabled: boolean;
}) {
  function handleFiles(list: FileList | null) {
    if (!list) return;
    const arr = Array.from(list).slice(0, 5);
    onChange(arr);
  }

  return (
    <div>
      <label
        className={
          'flex flex-col items-center justify-center border-2 border-dashed rounded-md p-8 cursor-pointer transition-colors ' +
          (disabled
            ? 'border-gray-200 bg-gray-50 cursor-not-allowed'
            : 'border-gray-300 hover:border-purple-400 hover:bg-purple-50')
        }
        onDragOver={(e) => {
          e.preventDefault();
        }}
        onDrop={(e) => {
          e.preventDefault();
          if (!disabled) handleFiles(e.dataTransfer.files);
        }}
      >
        <input
          type="file"
          accept=".log,.txt,.out,.gz"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
          disabled={disabled}
        />
        <p className="text-gray-700 font-medium">
          Drop log files here or click to choose
        </p>
        <p className="text-sm text-gray-500 mt-1">
          .log / .txt / .out / .gz — up to 5 files, 50&nbsp;MB total on the
          free tier
        </p>
      </label>
      {files.length > 0 && (
        <div className="mt-3 space-y-1">
          {files.map((f) => (
            <div key={f.name} className="text-sm text-gray-700 font-mono">
              {f.name} ({(f.size / 1024).toFixed(1)} KB)
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


function DiagnosisPanel({ diagnosis }: { diagnosis: Diagnosis }) {
  const confidenceColor =
    diagnosis.confidence === 'high'
      ? 'bg-green-100 text-green-800'
      : diagnosis.confidence === 'medium'
        ? 'bg-yellow-100 text-yellow-800'
        : 'bg-red-100 text-red-800';

  return (
    <div className="mt-8 border border-gray-200 rounded-md p-6 bg-white shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-2xl font-bold text-gray-900">Diagnosis</h2>
        <span
          className={`text-xs font-semibold uppercase tracking-wide px-2 py-1 rounded ${confidenceColor}`}
        >
          {diagnosis.confidence}
        </span>
      </div>

      <Section title="Likely cause" body={diagnosis.likely_cause} />
      <Section title="Recommended action" body={diagnosis.recommended_action} />
      {diagnosis.code_suggestion && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-1">
            Suggested SQL / shell
          </h3>
          <pre className="font-mono text-xs bg-gray-50 border border-gray-200 rounded p-3 overflow-x-auto">
            {diagnosis.code_suggestion}
          </pre>
        </div>
      )}
      {diagnosis.escalate_if && (
        <div className="mb-4 text-sm">
          <span className="font-semibold text-gray-700">Escalate if: </span>
          <span className="text-gray-700">{diagnosis.escalate_if}</span>
        </div>
      )}

      {/* "What we analyzed" footer */}
      <div className="mt-6 pt-4 border-t border-gray-200 text-xs text-gray-500">
        Analyzed {(diagnosis.analyzed_bytes / 1024).toFixed(1)} KB —
        extracted {diagnosis.extracted_line_count} relevant lines.
        {diagnosis.usage_remaining !== null && (
          <> {diagnosis.usage_remaining} of your daily analyses remaining.</>
        )}
        {diagnosis.usage_remaining === null && <> Unlimited on your tier.</>}
      </div>
    </div>
  );
}


function Section({ title, body }: { title: string; body: string }) {
  return (
    <div className="mb-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-1">{title}</h3>
      <p className="text-gray-900 whitespace-pre-wrap">{body}</p>
    </div>
  );
}
