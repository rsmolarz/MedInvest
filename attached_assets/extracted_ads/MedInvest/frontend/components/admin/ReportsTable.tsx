"use client";

import Link from "next/link";

export type Report = {
  id: number;
  entity_type: "post" | "comment";
  entity_id: number;
  reporter_user_id: number;
  reason: string | null;
  details: string | null;
  status: "open" | "resolved";
  resolution: string | null;
  created_at: string | null;
  resolved_at: string | null;
  resolved_by_id: number | null;
};

export default function ReportsTable({ reports }: { reports: Report[] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border">
      <table className="w-full text-sm">
        <thead className="border-b bg-white/5">
          <tr>
            <th className="px-4 py-3 text-left">Content</th>
            <th className="px-4 py-3 text-left">Reason</th>
            <th className="px-4 py-3 text-left">Reporter</th>
            <th className="px-4 py-3 text-left">Created</th>
            <th className="px-4 py-3 text-left">Status</th>
            <th className="px-4 py-3 text-left">Action</th>
          </tr>
        </thead>
        <tbody>
          {reports.map((r) => (
            <tr key={r.id} className="border-b last:border-0">
              <td className="px-4 py-3">
                <div className="font-medium">
                  {r.entity_type} #{r.entity_id}
                </div>
                <div className="text-xs opacity-70">Report #{r.id}</div>
              </td>
              <td className="px-4 py-3">
                <div className="capitalize">{r.reason || "—"}</div>
                {r.details ? <div className="mt-1 text-xs opacity-70 line-clamp-2">{r.details}</div> : null}
              </td>
              <td className="px-4 py-3">{r.reporter_user_id}</td>
              <td className="px-4 py-3">{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
              <td className="px-4 py-3">
                <span className={`rounded-full px-2 py-1 text-xs ${r.status === "open" ? "bg-yellow-500/20" : "bg-green-500/20"}`}>
                  {r.status}
                </span>
              </td>
              <td className="px-4 py-3">
                <Link className="underline" href={`/admin/reports/${r.id}`}>
                  Review
                </Link>
              </td>
            </tr>
          ))}
          {reports.length === 0 ? (
            <tr>
              <td className="px-4 py-8 text-center opacity-70" colSpan={6}>
                No reports.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
