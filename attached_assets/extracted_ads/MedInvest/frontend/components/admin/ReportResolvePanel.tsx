"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import type { Report } from "@/components/admin/ReportsTable";

type ResolveResponse = { ok: boolean; report: Report };

export default function ReportResolvePanel({ report, onResolved }: { report: Report; onResolved: (r: Report) => void }) {
  const [resolution, setResolution] = useState<"no_action" | "hide" | "lock">("no_action");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function resolve() {
    setLoading(true);
    setErr(null);
    try {
      const resp = await apiPost<ResolveResponse>(`/api/admin/reports/${report.id}/resolve`, { resolution });
      onResolved(resp.report);
    } catch (e: any) {
      setErr(e?.message || "Failed to resolve");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border p-4">
      <h2 className="text-lg font-semibold">Resolve</h2>
      <div className="mt-3 space-y-2 text-sm">
        <label className="flex items-center gap-2">
          <input type="radio" name="resolution" checked={resolution === "no_action"} onChange={() => setResolution("no_action")} />
          No action
        </label>
        <label className="flex items-center gap-2">
          <input type="radio" name="resolution" checked={resolution === "hide"} onChange={() => setResolution("hide")} />
          Hide content
        </label>
        <label className="flex items-center gap-2">
          <input type="radio" name="resolution" checked={resolution === "lock"} onChange={() => setResolution("lock")} />
          Lock thread (and hide)
        </label>
      </div>

      {err ? <div className="mt-3 rounded-lg border p-2 text-sm">{err}</div> : null}

      <button
        className="mt-4 rounded-xl border px-4 py-2 text-sm disabled:opacity-50"
        disabled={loading || report.status !== "open"}
        onClick={resolve}
      >
        {loading ? "Resolving…" : "Resolve report"}
      </button>
      {report.status !== "open" ? <div className="mt-2 text-xs opacity-70">Already resolved.</div> : null}
    </div>
  );
}
