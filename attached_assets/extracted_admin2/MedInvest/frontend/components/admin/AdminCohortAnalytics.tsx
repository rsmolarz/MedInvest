"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";

type CohortRow = { cohort: string; users: number; activated: number; activation_rate: number };

type CohortResponse = {
  window_days: number;
  by_specialty: CohortRow[];
  by_invite_source: CohortRow[];
};

function pct(x: number) {
  const v = isFinite(x) ? x : 0;
  return `${(v * 100).toFixed(1)}%`;
}

function Table({ title, rows }: { title: string; rows: CohortRow[] }) {
  return (
    <div className="rounded-2xl border p-4">
      <div className="text-base font-semibold">{title}</div>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="py-2 text-left">Cohort</th>
              <th className="py-2 text-right">Users</th>
              <th className="py-2 text-right">Activated</th>
              <th className="py-2 text-right">Activation</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.cohort} className="border-b last:border-b-0">
                <td className="py-2">{r.cohort}</td>
                <td className="py-2 text-right">{r.users}</td>
                <td className="py-2 text-right">{r.activated}</td>
                <td className="py-2 text-right">{pct(r.activation_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function AdminCohortAnalytics() {
  const [data, setData] = useState<CohortResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiGet<CohortResponse>("/api/admin/analytics/cohorts")
      .then((d) => {
        setData(d);
        setErr(null);
      })
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  return (
    <section className="p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Cohort Analytics</h1>
          <div className="text-sm opacity-70">Activation in last {data?.window_days ?? 30} days</div>
        </div>
        <Link className="text-sm underline" href="/admin/analytics">
          Back to overview
        </Link>
      </div>

      {err ? <div className="mt-4 rounded-lg border p-3 text-sm">{err}</div> : null}

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Table title="By Specialty" rows={data?.by_specialty ?? []} />
        <Table title="By Invite Source" rows={data?.by_invite_source ?? []} />
      </div>

      <div className="mt-6 rounded-2xl border p-4 text-sm opacity-80">
        Use this to decide where to spend invite credits and which specialties get boosted.
      </div>
    </section>
  );
}
