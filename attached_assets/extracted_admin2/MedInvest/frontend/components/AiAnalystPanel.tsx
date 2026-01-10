"use client";

import React, { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type DealResponse = {
  deal: {
    id: number;
    asset_class: string;
    strategy: string | null;
    location: string | null;
    thesis: string;
    key_risks: string | null;
  };
  post: { id: number; content: string | null; author_id: number | null; created_at: string | null };
  analyses: { id: number; provider: string | null; model: string | null; output_text: string; created_at: string | null }[];
};

type JobCreateResp = { status: string; job_id: number };
type JobResp = { id: number; status: string; output_text?: string | null; error?: string | null };

function randomKey(prefix = "ai") {
  return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now()}`;
}

export default function AiAnalystPanel({ dealId }: { dealId: number }) {
  const [deal, setDeal] = useState<DealResponse | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [jobOutput, setJobOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const dealPath = useMemo(() => `/api/deals/${dealId}`, [dealId]);

  useEffect(() => {
    let alive = true;
    setError(null);
    apiGet<DealResponse>(dealPath)
      .then((d) => {
        if (!alive) return;
        setDeal(d);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e.message || "Failed");
      });
    return () => {
      alive = false;
    };
  }, [dealPath]);

  // Poll job while pending
  useEffect(() => {
    if (!jobId) return;
    let alive = true;
    const interval = setInterval(() => {
      apiGet<JobResp>(`/api/ai/jobs/${jobId}`)
        .then((j) => {
          if (!alive) return;
          setJobStatus(j.status);
          if (j.status === "done") {
            setJobOutput(j.output_text || null);
            clearInterval(interval);
          }
          if (j.status === "failed") {
            setError(j.error || "Job failed");
            clearInterval(interval);
          }
        })
        .catch((e) => {
          if (!alive) return;
          setError(e.message || "Poll failed");
          clearInterval(interval);
        });
    }, 1500);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, [jobId]);

  async function runAnalysis() {
    setLoading(true);
    setError(null);
    setJobOutput(null);
    try {
      // Deterministic idempotency: one analysis per deal per session click
      const idempotencyKey = randomKey(`deal_${dealId}`);
      const resp = await apiPost<JobCreateResp>(
        `/api/ai/jobs`,
        { job_type: "analyze_deal", deal_id: dealId },
        { idempotencyKey }
      );
      setJobId(resp.job_id);
      setJobStatus(resp.status);
    } catch (e: any) {
      setError(e.message || "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>AI Analyst</h3>
        <button onClick={runAnalysis} disabled={loading} style={{ padding: "8px 10px" }}>
          {loading ? "Starting…" : "Run AI Analysis"}
        </button>
      </div>

      {error && <div style={{ color: "crimson", marginTop: 10 }}>{error}</div>}

      {jobId && (
        <div style={{ marginTop: 10, fontSize: 12, color: "#555" }}>
          Job: #{jobId} • Status: {jobStatus || "—"}
        </div>
      )}

      {jobOutput && (
        <div style={{ marginTop: 12, whiteSpace: "pre-wrap", lineHeight: 1.4 }}>
          {jobOutput}
        </div>
      )}

      {!jobOutput && deal?.analyses?.length ? (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, color: "#666", marginBottom: 8 }}>Latest saved analyses</div>
          {deal.analyses.slice(0, 2).map((a) => (
            <div key={a.id} style={{ border: "1px solid #eee", borderRadius: 10, padding: 10, marginBottom: 8 }}>
              <div style={{ fontSize: 12, color: "#555" }}>
                {a.created_at ? new Date(a.created_at).toLocaleString() : ""}
              </div>
              <div style={{ whiteSpace: "pre-wrap" }}>{a.output_text}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
