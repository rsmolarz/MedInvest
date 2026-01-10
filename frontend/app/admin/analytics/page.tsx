'use client';

import { useEffect, useState } from 'react';

interface AnalyticsData {
  verified_wau: number;
  deal_wau: number;
  time_to_first_value_hours_p50: number;
  verification_sla_hours: {
    p50: number;
    p95: number;
  };
  invites_7d: {
    issued: number;
    accepted: number;
    conversion_pct: number;
  };
  window: {
    start: string;
    end: string;
  };
}

function Card({ label, value, subtext }: { label: string; value: string | number; subtext?: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="text-sm font-medium text-gray-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold text-gray-900">{value}</div>
      {subtext && <div className="mt-1 text-xs text-gray-400">{subtext}</div>}
    </div>
  );
}

export default function AnalyticsOverview() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/admin/analytics/overview', { credentials: 'include' })
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load analytics');
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center text-red-600">
        <p>Error: {error}</p>
        <p className="text-sm text-gray-500 mt-2">Admin access required</p>
      </div>
    );
  }

  if (!data) return null;

  const windowStart = new Date(data.window.start).toLocaleDateString();
  const windowEnd = new Date(data.window.end).toLocaleDateString();

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Analytics Overview</h1>
        <p className="text-sm text-gray-500">
          {windowStart} — {windowEnd}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card
          label="Verified WAU"
          value={data.verified_wau}
          subtext="Active verified physicians"
        />
        <Card
          label="Deal WAU"
          value={data.deal_wau}
          subtext="Engaged with deals"
        />
        <Card
          label="TTFV (p50)"
          value={`${data.time_to_first_value_hours_p50}h`}
          subtext="Time to first value"
        />
        <Card
          label="Verification SLA"
          value={`${data.verification_sla_hours.p50}h`}
          subtext={`p95: ${data.verification_sla_hours.p95}h`}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card
          label="Invites Issued (7d)"
          value={data.invites_7d.issued}
        />
        <Card
          label="Invites Accepted (7d)"
          value={data.invites_7d.accepted}
        />
        <Card
          label="Invite Conversion"
          value={`${data.invites_7d.conversion_pct}%`}
          subtext="Accepted / Issued"
        />
      </div>

      <div className="mt-8 p-4 bg-gray-50 rounded-lg">
        <h2 className="font-semibold text-gray-700 mb-2">Quick Insights</h2>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>
            {data.verified_wau > 0 ? '✓' : '○'} Are we growing?{' '}
            <span className="font-medium">
              {data.verified_wau} verified physicians active this week
            </span>
          </li>
          <li>
            {data.verification_sla_hours.p50 < 24 ? '✓' : '⚠'} Is verification the bottleneck?{' '}
            <span className="font-medium">
              Median {data.verification_sla_hours.p50}h to approve
            </span>
          </li>
          <li>
            {data.deal_wau > 0 ? '✓' : '○'} Are doctors posting deals?{' '}
            <span className="font-medium">
              {data.deal_wau} engaged with deals this week
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
}
