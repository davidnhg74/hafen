import Link from 'next/link';

export default function FeaturesPage() {
  return (
    <div className="w-full">
      {/* Hero */}
      <section className="py-20 bg-gradient-to-br from-purple-900 to-blue-900 text-white">
        <div className="container mx-auto px-4 text-center">
          <h1 className="text-5xl font-bold mb-6">Powerful Migration Features</h1>
          <p className="text-xl text-purple-100 max-w-2xl mx-auto">
            Everything you need to migrate from Oracle to PostgreSQL with confidence
          </p>
        </div>
      </section>

      {/* Feature Categories */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          {/* Analysis */}
          <div className="mb-20">
            <h2 className="text-3xl font-bold text-gray-900 mb-12">Schema Analysis</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">📊</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Complexity Scoring</h3>
                <p className="text-gray-700">
                  AI-powered analysis identifies complex PL/SQL patterns, dependencies, and migration risks before
                  conversion.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">🔍</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Pattern Detection</h3>
                <p className="text-gray-700">
                  Detect database links, advanced queuing, spatial features, and other Oracle-specific constructs.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">⚠️</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Risk Assessment</h3>
                <p className="text-gray-700">
                  Flag semantic differences between Oracle and PostgreSQL that could cause runtime errors.
                </p>
              </div>
            </div>
          </div>

          {/* Conversion */}
          <div className="mb-20">
            <h2 className="text-3xl font-bold text-gray-900 mb-12">Code Conversion</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">🤖</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Neural Conversion</h3>
                <p className="text-gray-700">
                  LLM-powered conversion engine that understands PL/SQL semantics and translates to PostgreSQL idioms.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">📝</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Procedure & Function Conversion</h3>
                <p className="text-gray-700">
                  Convert CREATE OR REPLACE procedures, functions, packages, and triggers with semantic accuracy.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">🔄</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Intelligent Refactoring</h3>
                <p className="text-gray-700">
                  Automatically refactor cursor loops to PostgreSQL idioms, optimize EXECUTE IMMEDIATE patterns.
                </p>
              </div>
            </div>
          </div>

          {/* Migration Workflow */}
          <div className="mb-20">
            <h2 className="text-3xl font-bold text-gray-900 mb-12">Migration Workflow</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">👥</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">DBA Collaboration</h3>
                <p className="text-gray-700">
                  Multi-phase workflow with DBA review points, approvals, and sign-offs at each migration phase.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">✅</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Merkle Verification</h3>
                <p className="text-gray-700">
                  Every copied table is hashed on both source and target and compared root-to-root. Any discrepancy surfaces per-table before cutover.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">📋</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Runbook Generator</h3>
                <p className="text-gray-700">
                  Export a PDF runbook of the migration plan — schema steps, cutover checklist, and per-table load order — for stakeholder review and change control.
                </p>
              </div>
            </div>
          </div>

          {/* Ongoing Operations */}
          <div className="mb-20">
            <h2 className="text-3xl font-bold text-gray-900 mb-12">Ongoing Operations</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">🕐</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Scheduled Migrations</h3>
                <p className="text-gray-700">
                  Cron-driven recurring runs with IANA timezone support (DST-aware). Clone the template, run nightly, history stays intact.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">🎭</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Per-Column PII Masking</h3>
                <p className="text-gray-700">
                  Redact emails, SSNs, names before they land in staging. Deterministic HMAC-hash preserves foreign-key joins even when every value is masked.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">♻️</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Checkpoint & Resume</h3>
                <p className="text-gray-700">
                  Every batch is checkpointed by PK. A crashed run resumes at the last successful batch instead of restarting the whole load.
                </p>
              </div>
            </div>
          </div>

          {/* Integration */}
          <div>
            <h2 className="text-3xl font-bold text-gray-900 mb-12">Integration & Automation</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">🔑</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">REST API</h3>
                <p className="text-gray-700">
                  Complete REST API for programmatic access. Integrate migrations into your CI/CD pipeline.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">🪝</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Webhooks</h3>
                <p className="text-gray-700">
                  Fire signed HTTP requests on migration completion or failure. HMAC-SHA256 over the raw body so subscribers validate authenticity.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">🐍</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Python SDK</h3>
                <p className="text-gray-700">
                  <code className="rounded bg-gray-100 px-1 font-mono text-sm">pip install hafen-sdk</code> — typed client for scripted migrations and CI integration.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 bg-purple-600 text-white">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-4xl font-bold mb-6">Ready to migrate?</h2>
          <Link
            href="/download"
            className="inline-block px-8 py-4 bg-white text-purple-600 font-bold rounded-lg hover:bg-gray-100 transition"
          >
            Download Community
          </Link>
        </div>
      </section>
    </div>
  );
}
