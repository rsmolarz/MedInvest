"use client";

import { useEffect, useState } from "react";
import ReportsTable, { type Report } from "@/components/admin/ReportsTable";
import { apiGet } from "@/lib/api";

type ListResp = { reports: Report[] };

export default function AdminReportsPage() {
  const [status, setStatus] = useState<"open" | "resolved">("open");
  const [reports, setReports] = useState<Report[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setErr(null);
    apiGet<ListResp>(`/api/admin/reports?status=${status}`)
      .then((d) => {
        if (!mounted) return;
        setReports(d.reports || []);
      })
      .catch((e) => {
        if (!mounted) return;
        setErr(e.message || "Failed to load");
      });
    return () => {
      mounted = false;
    };
  }, [status]);

  return (
    <main className="p-6">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold">Reports</h1>
        <div className="flex gap-2 text-sm">
          <button
            className={`rounded-xl border px-3 py-1 ${status === "open" ? "bg-white/10" : "opacity-80"}`}
            onClick={() => setStatus("open")}
          >
            Open
          </button>
          <button
            className={`rounded-xl border px-3 py-1 ${status === "resolved" ? "bg-white/10" : "opacity-80"}`}
            onClick={() => setStatus("resolved")}
          >
            Resolved
          </button>
        </div>
      </div>

      {err ? <div className="mt-4 rounded-lg border p-3 text-sm">{err}</div> : null}

      <div className="mt-6">
        <ReportsTable reports={reports} />
      </div>
    </main>
  );
}
