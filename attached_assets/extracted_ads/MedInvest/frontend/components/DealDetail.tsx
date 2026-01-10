"use client";

import React, { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import DealMemoryPanel from "@/components/DealMemoryPanel";

type DealResponse = {
  deal: {
    id: number;
    asset_class: string;
    strategy: string | null;
    location: string | null;
    time_horizon_months: number | null;
    target_irr: number | null;
    target_multiple: number | null;
    minimum_investment: number | null;
    sponsor_name: string | null;
    thesis: string;
    key_risks: string | null;
    diligence_needed: string | null;
    status: string;
  };
  post: { id: number; content: string | null; created_at: string | null };
  analyses: any[];
};

export default function DealDetail({ dealId }: { dealId: number }) {
  const [d, setD] = useState<DealResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    apiGet<DealResponse>(`/api/deals/${dealId}`)
      .then((resp) => {
        if (!alive) return;
        setD(resp);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e.message || "Failed");
      });
    return () => {
      alive = false;
    };
  }, [dealId]);

  if (error) return <div style={{ color: "crimson" }}>{error}</div>;
  if (!d) return <div>Loading…</div>;

  const deal = d.deal;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Deal</h2>
      <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 14 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", fontSize: 13, color: "#444" }}>
          <span><b>Asset:</b> {deal.asset_class}</span>
          <span><b>Strategy:</b> {deal.strategy || "—"}</span>
          <span><b>Location:</b> {deal.location || "—"}</span>
          <span><b>Status:</b> {deal.status}</span>
        </div>
        <div style={{ marginTop: 12, whiteSpace: "pre-wrap", lineHeight: 1.4 }}>
          <h3 style={{ margin: "0 0 6px 0" }}>Thesis</h3>
          {deal.thesis}
        </div>
        {deal.key_risks && (
          <div style={{ marginTop: 12, whiteSpace: "pre-wrap" }}>
            <h3 style={{ margin: "0 0 6px 0" }}>Key risks</h3>
            {deal.key_risks}
          </div>
        )}
        {deal.diligence_needed && (
          <div style={{ marginTop: 12, whiteSpace: "pre-wrap" }}>
            <h3 style={{ margin: "0 0 6px 0" }}>Diligence needed</h3>
            {deal.diligence_needed}
          </div>
        )}
      </div>

      <DealMemoryPanel dealId={dealId} />
    </div>
  );
}
