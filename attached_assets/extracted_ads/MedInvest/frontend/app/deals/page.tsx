'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/api';

type DealRow = {
  id: number;
  asset_class: string;
  strategy?: string;
  location?: string;
  thesis?: string;
  status?: string;
  created_at?: string;
  signal_score?: number;
};

export default function DealsPage() {
  const [tab, setTab] = useState<'trending' | 'new'>('trending');
  const [rows, setRows] = useState<DealRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setErr(null);
    const qs = tab === 'trending' ? '?sort=trending&limit=25' : '?sort=new&limit=25';
    const res = await apiFetch(`/api/deals${qs}`);
    if (!res.ok) {
      setErr('Failed to load deals');
      return;
    }
    const j = await res.json();
    setRows(j.results || []);
  }

  useEffect(() => {
    load();
  }, [tab]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Deals</h1>
        <Link href="/deals/new">Post a Deal</Link>
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <button onClick={() => setTab('trending')} disabled={tab === 'trending'}>Trending</button>
        <button onClick={() => setTab('new')} disabled={tab === 'new'}>New</button>
      </div>

      {err && <div style={{ marginTop: 12, color: 'tomato' }}>{err}</div>}

      <div style={{ marginTop: 16 }}>
        {rows.map((d) => (
          <div key={d.id} style={{ padding: 12, border: '1px solid #333', borderRadius: 8, marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Link href={`/deals/${d.id}`}><strong>{d.asset_class}</strong> — {d.strategy || '—'}</Link>
              {typeof d.signal_score === 'number' && <div style={{ opacity: 0.8 }}>Score: {d.signal_score.toFixed(2)}</div>}
            </div>
            <div style={{ marginTop: 6, opacity: 0.85 }}>{d.location || ''}</div>
            <div style={{ marginTop: 8, whiteSpace: 'pre-wrap', opacity: 0.9 }}>
              {(d.thesis || '').slice(0, 240)}{(d.thesis || '').length > 240 ? '…' : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
