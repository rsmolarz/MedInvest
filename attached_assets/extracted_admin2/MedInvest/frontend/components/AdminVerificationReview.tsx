"use client";

import React, { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type VerificationUser = {
  user_id: number;
  full_name: string;
  email: string;
  specialty: string | null;
  medical_license: string | null;
  npi_number: string | null;
  license_state: string | null;
  role: string | null;
  verification_status: string | null;
  submitted_at: string | null;
  verified_at: string | null;
  verification_notes: string | null;
  created_at: string | null;
};

export default function AdminVerificationReview({ userId }: { userId: number }) {
  const [u, setU] = useState<VerificationUser | null>(null);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    apiGet<VerificationUser>(`/api/admin/verification/${userId}`)
      .then((d) => {
        if (!alive) return;
        setU(d);
        setNotes(d.verification_notes || "");
      })
      .catch((e) => {
        if (!alive) return;
        setError(e.message || "Failed");
      });
    return () => {
      alive = false;
    };
  }, [userId]);

  async function approve() {
    setLoading(true);
    setToast(null);
    try {
      await apiPost(`/api/admin/verification/${userId}/approve`, {});
      setToast("Approved");
      // Auto-advance: go back to queue (your UI can implement next-id; this keeps it simple)
      window.location.href = "/admin/verification";
    } catch (e: any) {
      setError(e.message || "Failed");
    } finally {
      setLoading(false);
    }
  }

  async function reject() {
    if (!notes.trim()) {
      setError("Rejection requires notes.");
      return;
    }
    setLoading(true);
    setToast(null);
    try {
      await apiPost(`/api/admin/verification/${userId}/reject`, { notes });
      setToast("Rejected");
      window.location.href = "/admin/verification";
    } catch (e: any) {
      setError(e.message || "Failed");
    } finally {
      setLoading(false);
    }
  }

  if (error) return <div style={{ color: "crimson" }}>{error}</div>;
  if (!u) return <div>Loading…</div>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Verification Review</h2>
      {toast && <div style={{ color: "#0a7" }}>{toast}</div>}

      <div style={{ border: "1px solid #ddd", borderRadius: 10, padding: 14, marginBottom: 12 }}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>{u.full_name}</div>
        <div style={{ color: "#555" }}>{u.email}</div>
        <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div><b>Specialty:</b> {u.specialty || "—"}</div>
          <div><b>License:</b> {u.medical_license || "—"}</div>
          <div><b>NPI:</b> {u.npi_number || "—"}</div>
          <div><b>State:</b> {u.license_state || "—"}</div>
          <div><b>Status:</b> {u.verification_status || "—"}</div>
          <div><b>Submitted:</b> {u.submitted_at ? new Date(u.submitted_at).toLocaleString() : "—"}</div>
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: "block", fontWeight: 600, marginBottom: 6 }}>Admin notes (required for reject)</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={4}
          style={{ width: "100%", padding: 10 }}
          placeholder="Reason for rejection, issues found, follow-ups needed…"
        />
      </div>

      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={approve} disabled={loading} style={{ padding: "10px 12px" }}>
          Approve
        </button>
        <button onClick={reject} disabled={loading} style={{ padding: "10px 12px" }}>
          Reject
        </button>
        <a href="/admin/verification" style={{ alignSelf: "center" }}>
          Back to queue
        </a>
      </div>
    </div>
  );
}
