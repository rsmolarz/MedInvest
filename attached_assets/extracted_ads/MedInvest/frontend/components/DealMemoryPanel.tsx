"use client";

import React, { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type MemoryItem = {
  deal_id: number | null;
  post_id: number | null;
  title: string | null;
  asset_class: string | null;
  strategy: string | null;
  location: string | null;
  outcome: string;
  key_lessons: string;
  what_went_right?: string | null;
  what_went_wrong?: string | null;
  created_at?: string | null;
};

type MemoryResponse = { deal_id: number; items: MemoryItem[] };

export default function DealMemoryPanel({ dealId }: { dealId: number }) {
  const [resp, setResp] = useState<MemoryResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setErr(null);
    apiGet<MemoryResponse>(`/api/deals/${dealId}/memory`)
      .then((r) => {
        if (!alive) return;
        setResp(r);
      })
      .catch((e) => {
        if (!alive) return;
        setErr(e.message || "Failed");
      });
    return () => {
      alive = false;
    };
  }, [dealId]);

  if (err) {
    return (
      <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 14, marginTop: 16 }}>
        <h3 style={{ margin: "0 0 8px 0" }}>Deal memory</h3>
        <div style={{ color: "crimson" }}>{err}</div>
      </div>
    );
  }

  const items = resp?.items || [];

  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 14, marginTop: 16 }}>
      <h3 style={{ margin: "0 0 8px 0" }}>Deal memory</h3>
      <div style={{ fontSize: 13, color: "#444", marginBottom: 10 }}>
        Prior similar deals (same asset class) with outcomes and lessons learned.
      </div>
      {items.length === 0 ? (
        <div style={{ fontSize: 13, opacity: 0.8 }}>No similar outcomes recorded yet.</div>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {items.map((it, idx) => (
            <div key={idx} style={{ padding: 12, borderRadius: 10, background: "#f7f7f7" }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>{it.title || `Deal #${it.deal_id}`}</div>
              <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 8 }}>
                outcome: <b>{it.outcome}</b>
                {it.location ? ` • ${it.location}` : ""}
                {it.strategy ? ` • ${it.strategy}` : ""}
              </div>
              <div style={{ whiteSpace: "pre-wrap", fontSize: 13, lineHeight: 1.35 }}>
                <b>Lessons:</b> {it.key_lessons}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
