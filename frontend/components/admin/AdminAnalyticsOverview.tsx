"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";

type OverviewResponse = {
  window_days: number;
  cards: {
    verified_wau: number;
    deal_wau: number;
    time_to_first_value_p50_hours: number | null;
    verification_sla_p50_hours: number | null;
    verification_sla_p95_hours: number | null;
    invites_issued_7d: number;
    invites_accepted_7d: number;
  };
};

function Card({ title, value, sub }: { title: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border p-4 shadow-sm">
      <div className="text-sm opacity-80">{title}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub ? <div className="mt-1 text-xs opacity-70">{sub}</div> : null}
    </div>
  );
}

function fmtHours(v: number | null): string {
  if (v === null || Number.isNaN(v)) return "—";
  if (v < 1) return `${Math.round(v * 60)}m`;
  return `${v.toFixed(1)}h`;
}

export default function AdminAnalyticsOverview() {
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    apiGet<OverviewResponse>("/api/admin/analytics/overview")
      .then((d) => {
        if (!mounted) return;
        setData(d);
        setErr(null);
      })
      .catch((e) => {
        if (!mounted) return;
        setErr(e.message || "Failed to load");
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <section className="p-6">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold">Analytics overview</h1>
        <Link className="text-sm underline" href="/admin/analytics/cohorts">
          View cohorts
        </Link>
      </div>

      {err ? <div className="mt-4 rounded-lg border p-3 text-sm">{err}</div> : null}

      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card title="Verified WAU" value={data ? String(data.cards.verified_wau) : "—"} sub={`Last ${data?.window_days ?? 7} days`} />
        <Card title="Deal WAU" value={data ? String(data.cards.deal_wau) : "—"} sub={`Last ${data?.window_days ?? 7} days`} />
        <Card title="Time to first value (p50)" value={data ? fmtHours(data.cards.time_to_first_value_p50_hours) : "—"} sub="From verified → first deal/analysis" />
        <Card title="Verification SLA (p50)" value={data ? fmtHours(data.cards.verification_sla_p50_hours) : "—"} sub="Submitted → verified" />
        <Card title="Verification SLA (p95)" value={data ? fmtHours(data.cards.verification_sla_p95_hours) : "—"} sub="Submitted → verified" />
        <Card title="Invites (7d)" value={data ? `${data.cards.invites_issued_7d} / ${data.cards.invites_accepted_7d}` : "—"} sub="Issued / accepted" />
      </div>

      <div className="mt-6 rounded-2xl border p-4 text-sm opacity-80">
        High-leverage action: keep verification SLA under threshold. If SLA breaches, enable auto-routing and add reviewers.
      </div>
    </section>
  );
}
