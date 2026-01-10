"use client";

import React, { useMemo, useState } from "react";
import AdminNav from "@/components/admin/AdminNav";

export default function AdminAuditPage() {
  const [days, setDays] = useState<number>(30);
  const [format, setFormat] = useState<"csv" | "pdf">("csv");

  const href = useMemo(() => {
    const d = Math.max(1, Math.min(days || 30, 365));
    const f = format || "csv";
    return `/api/admin/audit/export?format=${encodeURIComponent(f)}&days=${encodeURIComponent(String(d))}`;
  }, [days, format]);

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      <div className="mx-auto grid max-w-6xl grid-cols-[260px_1fr] gap-6">
        <aside className="border-r border-white/10 min-h-screen">
          <AdminNav />
        </aside>

        <main className="p-6">
          <h1 className="text-xl font-semibold">Audit export</h1>
          <p className="mt-2 text-sm opacity-80">
            One-click export of moderation + trust events (reports, report actions, verification queue, invites).
          </p>

          <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="grid grid-cols-2 gap-3 max-w-lg">
              <label className="text-sm">
                <div className="opacity-80 mb-1">Format</div>
                <select
                  className="w-full rounded-xl bg-black/40 border border-white/10 px-3 py-2"
                  value={format}
                  onChange={(e) => setFormat(e.target.value as any)}
                >
                  <option value="csv">CSV</option>
                  <option value="pdf">PDF</option>
                </select>
              </label>
              <label className="text-sm">
                <div className="opacity-80 mb-1">Window (days)</div>
                <input
                  className="w-full rounded-xl bg-black/40 border border-white/10 px-3 py-2"
                  type="number"
                  min={1}
                  max={365}
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value))}
                />
              </label>
            </div>

            <a
              href={href}
              className="inline-block mt-4 rounded-xl bg-white text-black px-4 py-2 text-sm font-semibold"
            >
              Download export
            </a>

            <div className="mt-3 text-xs opacity-70">
              Note: exports are capped to 5,000 rows per section for safety.
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
