'use client';

import Navigation from '../components/Navigation';
import CostCalculator from '../components/CostCalculator';

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      {/* Header */}
      <header className="bg-white border-b border-gray-200 py-12">
        <div className="container mx-auto px-4 text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Calculate Your Savings
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Use our interactive calculator to see exactly how much you'll save by
            migrating from Oracle to PostgreSQL. Get a breakdown of costs, ROI, and
            payback period.
          </p>
        </div>
      </header>

      {/* Calculator */}
      <main className="container mx-auto px-4 py-12">
        <CostCalculator />
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
