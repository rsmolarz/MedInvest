"use client";

import React, { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";

type PendingItem = {
  user_id: number;
  full_name: string;
  email: string;
  npi_number: string | null;
  license_state: string | null;
  specialty: string | null;
  submitted_at: string | null;
};

type PendingResponse = { total: number; results: PendingItem[] };

export default function AdminVerificationTable() {
  const [limit] = useState(25);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [data, setData] = useState<PendingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    if (search.trim()) params.set("search", search.trim());
    return `/api/admin/verification/pending?${params.toString()}`;
  }, [limit, offset, search]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    apiGet<PendingResponse>(query)
      .then((d) => {
        if (!alive) return;
        setData(d);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e.message || "Failed");
      })
      .finally(() => {
        if (!alive) return;
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [query]);

  const total = data?.total ?? 0;
  const pageStart = offset + 1;
  const pageEnd = Math.min(offset + limit, total);

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Pending Verifications</h2>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
        <input
          value={search}
          onChange={(e) => {
            setOffset(0);
            setSearch(e.target.value);
          }}
          placeholder="Search name, email, NPI"
          style={{ padding: 8, width: 320 }}
        />
        <div style={{ fontSize: 12, color: "#555" }}>
          {loading ? "Loading…" : total ? `Showing ${pageStart}-${pageEnd} of ${total}` : "No pending"}
        </div>
      </div>

      {error && <div style={{ color: "crimson", marginBottom: 12 }}>{error}</div>}

      <div style={{ border: "1px solid #ddd", borderRadius: 8, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f7f7f7", textAlign: "left" }}>
              <th style={{ padding: 10 }}>Name</th>
              <th style={{ padding: 10 }}>Specialty</th>
              <th style={{ padding: 10 }}>State</th>
              <th style={{ padding: 10 }}>NPI</th>
              <th style={{ padding: 10 }}>Submitted</th>
              <th style={{ padding: 10 }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {(data?.results || []).map((u) => (
              <tr key={u.user_id} style={{ borderTop: "1px solid #eee" }}>
                <td style={{ padding: 10 }}>
                  <div style={{ fontWeight: 600 }}>{u.full_name}</div>
                  <div style={{ fontSize: 12, color: "#666" }}>{u.email}</div>
                </td>
                <td style={{ padding: 10 }}>{u.specialty || "—"}</td>
                <td style={{ padding: 10 }}>{u.license_state || "—"}</td>
                <td style={{ padding: 10 }}>{u.npi_number || "—"}</td>
                <td style={{ padding: 10, fontSize: 12 }}>{u.submitted_at ? new Date(u.submitted_at).toLocaleString() : "—"}</td>
                <td style={{ padding: 10 }}>
                  <a href={`/admin/verification/${u.user_id}`}>Review</a>
                </td>
              </tr>
            ))}
            {!loading && (data?.results || []).length === 0 && (
              <tr>
                <td colSpan={6} style={{ padding: 14, color: "#666" }}>
                  No pending verifications.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 12 }}>
        <button
          onClick={() => setOffset(Math.max(0, offset - limit))}
          disabled={offset === 0 || loading}
          style={{ padding: "8px 10px" }}
        >
          Prev
        </button>
        <button
          onClick={() => setOffset(offset + limit)}
          disabled={loading || offset + limit >= total}
          style={{ padding: "8px 10px" }}
        >
          Next
        </button>
      </div>
    </div>
  );
}
