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
                <h3 className="text-xl font-bold text-gray-900 mb-2">Testing & Validation</h3>
                <p className="text-gray-700">
                  Dual-run testing compares output from Oracle and PostgreSQL side-by-side before cutover.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">📋</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Migration Planning</h3>
                <p className="text-gray-700">
                  Generate detailed migration plans with data migration strategies, cutover windows, and rollback plans.
                </p>
              </div>
            </div>
          </div>

          {/* Performance */}
          <div className="mb-20">
            <h2 className="text-3xl font-bold text-gray-900 mb-12">Performance & Optimization</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">📈</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Baseline Benchmarking</h3>
                <p className="text-gray-700">
                  Capture Oracle performance metrics before migration and compare against PostgreSQL post-migration.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">⚡</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Query Optimization</h3>
                <p className="text-gray-700">
                  Identify and optimize slow queries, missing indexes, and suboptimal execution plans on PostgreSQL.
                </p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">🎯</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Tuning Recommendations</h3>
                <p className="text-gray-700">
                  AI-driven recommendations for configuration tuning, connection pooling, and performance settings.
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
                <div className="text-4xl mb-4">🔐</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">API Keys</h3>
                <p className="text-gray-700">Generate and manage secure API keys for automation and third-party integrations.</p>
              </div>

              <div className="bg-white p-8 rounded-lg shadow border border-gray-200">
                <div className="text-4xl mb-4">📧</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">Notifications</h3>
                <p className="text-gray-700">
                  Email and Slack notifications for migration milestones, approvals, and issues.
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
            href="/signup"
            className="inline-block px-8 py-4 bg-white text-purple-600 font-bold rounded-lg hover:bg-gray-100 transition"
          >
            Start Your Free Trial
          </Link>
        </div>
      </section>
    </div>
  );
}
