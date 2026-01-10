"use client";

import React, { useEffect, useMemo, useState } from "react";
import AdminNav from "@/components/admin/AdminNav";
import { apiGet, apiPost } from "@/lib/api";

type Playbook = {
  id: number;
  cohort_dimension: string;
  cohort_value: string;
  title: string;
  guidelines: string;
  escalation_steps: string | null;
  examples_allowed: string | null;
  examples_disallowed: string | null;
  updated_at: string | null;
};

export default function PlaybooksPage() {
  const [rows, setRows] = useState<Playbook[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    cohort_dimension: "specialty",
    cohort_value: "",
    title: "",
    guidelines: "",
    escalation_steps: "",
    examples_allowed: "",
    examples_disallowed: "",
  });

  const canSubmit = useMemo(() => {
    return (
      form.cohort_dimension.trim().length > 0 &&
      form.cohort_value.trim().length > 0 &&
      form.title.trim().length > 0 &&
      form.guidelines.trim().length > 0
    );
  }, [form]);

  const load = () => {
    setErr(null);
    apiGet<{ playbooks: Playbook[] }>("/api/admin/moderation/playbooks")
      .then((r) => setRows(r.playbooks || []))
      .catch((e) => setErr(e.message || "Failed"));
  };

  useEffect(() => {
    load();
  }, []);

  const submit = async () => {
    if (!canSubmit) return;
    setSaving(true);
    setErr(null);
    try {
      await apiPost("/api/admin/moderation/playbooks", {
        cohort_dimension: form.cohort_dimension,
        cohort_value: form.cohort_value,
        title: form.title,
        guidelines: form.guidelines,
        escalation_steps: form.escalation_steps || null,
        examples_allowed: form.examples_allowed || null,
        examples_disallowed: form.examples_disallowed || null,
      });
      setForm({
        cohort_dimension: form.cohort_dimension,
        cohort_value: "",
        title: "",
        guidelines: "",
        escalation_steps: "",
        examples_allowed: "",
        examples_disallowed: "",
      });
      load();
    } catch (e: any) {
      setErr(e?.message || "Failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      <div className="mx-auto grid max-w-6xl grid-cols-[260px_1fr] gap-6">
        <aside className="border-r border-white/10 min-h-screen">
          <AdminNav />
        </aside>

        <main className="p-6">
          <h1 className="text-xl font-semibold">Moderator playbooks</h1>
          <p className="mt-2 text-sm opacity-80">
            Cohort-specific guidance for reviewers (not enforcement thresholds). One playbook per cohort.
          </p>

          {err && <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm">{err}</div>}

          <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">
                <div className="opacity-80 mb-1">Dimension</div>
                <input
                  className="w-full rounded-xl bg-black/40 border border-white/10 px-3 py-2"
                  value={form.cohort_dimension}
                  onChange={(e) => setForm((f) => ({ ...f, cohort_dimension: e.target.value }))}
                  placeholder="specialty | role | sponsor"
                />
              </label>
              <label className="text-sm">
                <div className="opacity-80 mb-1">Value</div>
                <input
                  className="w-full rounded-xl bg-black/40 border border-white/10 px-3 py-2"
                  value={form.cohort_value}
                  onChange={(e) => setForm((f) => ({ ...f, cohort_value: e.target.value }))}
                  placeholder="ENT, IM, Resident, Sponsor, ..."
                />
              </label>
            </div>

            <label className="text-sm block mt-3">
              <div className="opacity-80 mb-1">Title</div>
              <input
                className="w-full rounded-xl bg-black/40 border border-white/10 px-3 py-2"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="ENT community norms"
              />
            </label>

            <label className="text-sm block mt-3">
              <div className="opacity-80 mb-1">Guidelines (required)</div>
              <textarea
                className="w-full min-h-[140px] rounded-xl bg-black/40 border border-white/10 px-3 py-2"
                value={form.guidelines}
                onChange={(e) => setForm((f) => ({ ...f, guidelines: e.target.value }))}
                placeholder="Write in plain language. Include what to allow, what to remove, and what to escalate."
              />
            </label>

            <div className="grid grid-cols-2 gap-3 mt-3">
              <label className="text-sm">
                <div className="opacity-80 mb-1">Examples allowed</div>
                <textarea
                  className="w-full min-h-[100px] rounded-xl bg-black/40 border border-white/10 px-3 py-2"
                  value={form.examples_allowed}
                  onChange={(e) => setForm((f) => ({ ...f, examples_allowed: e.target.value }))}
                />
              </label>
              <label className="text-sm">
                <div className="opacity-80 mb-1">Examples disallowed</div>
                <textarea
                  className="w-full min-h-[100px] rounded-xl bg-black/40 border border-white/10 px-3 py-2"
                  value={form.examples_disallowed}
                  onChange={(e) => setForm((f) => ({ ...f, examples_disallowed: e.target.value }))}
                />
              </label>
            </div>

            <label className="text-sm block mt-3">
              <div className="opacity-80 mb-1">Escalation steps</div>
              <textarea
                className="w-full min-h-[100px] rounded-xl bg-black/40 border border-white/10 px-3 py-2"
                value={form.escalation_steps}
                onChange={(e) => setForm((f) => ({ ...f, escalation_steps: e.target.value }))}
                placeholder="When to warn, hide, lock; when to escalate to legal/compliance."
              />
            </label>

            <button
              className="mt-4 rounded-xl bg-white text-black px-4 py-2 text-sm font-semibold disabled:opacity-50"
              disabled={!canSubmit || saving}
              onClick={submit}
            >
              {saving ? "Saving…" : "Save playbook"}
            </button>
          </div>

          <div className="mt-6 rounded-2xl border border-white/10 overflow-hidden">
            <div className="px-4 py-3 text-sm font-semibold bg-white/5">Existing</div>
            <div className="divide-y divide-white/10">
              {rows.map((p) => (
                <div key={p.id} className="px-4 py-3">
                  <div className="text-sm font-semibold">
                    {p.cohort_dimension}:{p.cohort_value} — {p.title}
                  </div>
                  <div className="text-xs opacity-75 mt-1">Updated: {p.updated_at || "—"}</div>
                  <div className="mt-2 text-sm whitespace-pre-wrap opacity-90">{p.guidelines}</div>
                </div>
              ))}
              {rows.length === 0 && <div className="px-4 py-6 text-sm opacity-80">No playbooks yet.</div>}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
