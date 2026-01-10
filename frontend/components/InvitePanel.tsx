'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

type InviteRow = {
  id: number;
  code: string;
  invitee_email?: string;
  status: string;
  created_at?: string;
  expires_at?: string;
  accepted_at?: string;
};

export default function InvitePanel() {
  const [inviteeEmail, setInviteeEmail] = useState('');
  const [credits, setCredits] = useState<number>(0);
  const [rows, setRows] = useState<InviteRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setErr(null);
    const res = await apiFetch('/api/invites');
    if (!res.ok) {
      setErr('Failed to load invites');
      return;
    }
    const j = await res.json();
    setCredits(j.invite_credits || 0);
    setRows(j.results || []);
  }

  async function createInvite() {
    setErr(null);
    const res = await apiFetch('/api/invites', {
      method: 'POST',
      body: JSON.stringify({ invitee_email: inviteeEmail || null }),
    });
    const j = await res.json().catch(() => ({}));
    if (!res.ok) {
      setErr(j?.error || 'Failed to create invite');
      return;
    }
    setInviteeEmail('');
    await load();
  }

  useEffect(() => { load(); }, []);

  const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';

  return (
    <div style={{ maxWidth: 720 }}>
      <h1>Invites</h1>
      <div style={{ marginTop: 8, opacity: 0.9 }}>Remaining invites: <strong>{credits}</strong></div>

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <input
          value={inviteeEmail}
          onChange={(e) => setInviteeEmail(e.target.value)}
          placeholder="Optional: colleague email"
          style={{ flex: 1 }}
        />
        <button onClick={createInvite} disabled={credits <= 0}>Create</button>
      </div>

      {err && <div style={{ marginTop: 12, color: 'tomato' }}>{err}</div>}

      <div style={{ marginTop: 18 }}>
        {rows.map((i) => (
          <div key={i.id} style={{ padding: 12, border: '1px solid #333', borderRadius: 8, marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <strong>{i.status.toUpperCase()}</strong>
              <button
                onClick={() => navigator.clipboard.writeText(`${baseUrl}/signup?invite=${i.code}`)}
                type="button"
              >
                Copy link
              </button>
            </div>
            <div style={{ marginTop: 6, fontFamily: 'monospace' }}>{i.code}</div>
            <div style={{ marginTop: 6, opacity: 0.85 }}>
              {i.invitee_email ? `Email: ${i.invitee_email}` : 'Email: —'}
            </div>
            <div style={{ marginTop: 6, opacity: 0.85 }}>
              Expires: {i.expires_at || '—'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
