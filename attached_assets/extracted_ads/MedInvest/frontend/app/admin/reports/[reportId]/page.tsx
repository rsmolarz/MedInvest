"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { Report } from "@/components/admin/ReportsTable";
import ReportResolvePanel from "@/components/admin/ReportResolvePanel";

type ListResp = { reports: Report[] };

export default function AdminReportDetailPage() {
  const params = useParams() as { reportId: string };
  const reportId = Number(params.reportId);
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    setErr(null);
    // There is no dedicated GET-by-id endpoint yet; fetch open then resolved.
    const open = await apiGet<ListResp>("/api/admin/reports?status=open").catch(() => ({ reports: [] } as ListResp));
    const foundOpen = (open.reports || []).find((r) => r.id === reportId);
    if (foundOpen) {
      setReport(foundOpen);
      return;
    }
    const resolved = await apiGet<ListResp>("/api/admin/reports?status=resolved").catch(() => ({ reports: [] } as ListResp));
    const foundResolved = (resolved.reports || []).find((r) => r.id === reportId);
    if (foundResolved) {
      setReport(foundResolved);
      return;
    }
    setReport(null);
    setErr("Report not found");
  };

  useEffect(() => {
    if (!Number.isFinite(reportId)) return;
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId]);

  const createdLabel = useMemo(() => (report?.created_at ? new Date(report.created_at).toLocaleString() : "—"), [report?.created_at]);

  return (
    <main className="p-6">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <div className="text-sm opacity-80">
            <Link className="underline" href="/admin/reports">
              Reports
            </Link>
            <span className="opacity-60"> / </span>
            <span className="opacity-80">#{reportId}</span>
          </div>
          <h1 className="mt-1 text-2xl font-semibold">Report #{reportId}</h1>
        </div>
        <button className="rounded-xl border px-3 py-2 text-sm" onClick={() => router.back()}>
          Back
        </button>
      </div>

      {err ? <div className="mt-4 rounded-lg border p-3 text-sm">{err}</div> : null}

      {report ? (
        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-4">
            <div className="rounded-2xl border p-4">
              <div className="text-sm opacity-80">Content</div>
              <div className="mt-1 text-lg font-semibold">
                {report.entity_type} #{report.entity_id}
              </div>
              <div className="mt-2 text-sm">
                <div>
                  <span className="opacity-70">Reason:</span> <span className="capitalize">{report.reason || "—"}</span>
                </div>
                <div className="mt-1">
                  <span className="opacity-70">Reporter:</span> {report.reporter_user_id}
                </div>
                <div className="mt-1">
                  <span className="opacity-70">Created:</span> {createdLabel}
                </div>
                <div className="mt-1">
                  <span className="opacity-70">Status:</span> {report.status}
                  {report.resolution ? <span className="opacity-70"> · Resolution:</span> : null} {report.resolution || ""}
                </div>
              </div>

              {report.details ? (
                <div className="mt-3 rounded-xl border p-3 text-sm">
                  <div className="text-xs font-semibold uppercase opacity-70">Details</div>
                  <div className="mt-1 whitespace-pre-wrap">{report.details}</div>
                </div>
              ) : null}

              <div className="mt-3 text-xs opacity-70">
                Tip: add a GET-by-id endpoint later to avoid list-scanning.
              </div>
            </div>
          </div>
          <div>
            <ReportResolvePanel
              report={report}
              onResolved={(r) => {
                setReport(r);
              }}
            />
          </div>
        </div>
      ) : null}
    </main>
  );
}
