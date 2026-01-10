'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/api';

type DigestItem = {
  item_type: 'deal' | 'comment' | 'summary';
  entity_id?: number | null;
  rank?: number | null;
  payload?: any;
};

type Digest = {
  id: number;
  period_start?: string;
  period_end?: string;
  created_at?: string;
};

export default function WeeklyDigestCard() {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [items, setItems] = useState<DigestItem[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setErr(null);
    const res = await apiFetch('/api/digests/latest');
    if (!res.ok) {
      setErr('No digest yet');
      return;
    }
    const j = await res.json();
    setDigest(j.digest);
    setItems(j.items || []);
  }

  useEffect(() => { load(); }, []);

  if (err) return <div style={{ padding: 12, border: '1px solid #333', borderRadius: 8 }}>{err}</div>;
  if (!digest) return <div style={{ padding: 12, border: '1px solid #333', borderRadius: 8 }}>Loading digest…</div>;

  const summary = items.find((i) => i.item_type === 'summary')?.payload?.summary;

  const topDeals = items.filter((i) => i.item_type === 'deal').slice(0, 3);
  return (
    <div style={{ padding: 12, border: '1px solid #333', borderRadius: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <strong>Weekly Signal Digest</strong>
        <Link href={`/digests/${digest.id}`}>Open</Link>
      </div>
      {summary && <div style={{ marginTop: 8, opacity: 0.9 }}>{summary}</div>}
      <div style={{ marginTop: 10 }}>
        {topDeals.map((d, idx) => (
          <div key={idx} style={{ marginTop: 6 }}>
            <Link href={`/deals/${d.entity_id}`}>Deal #{idx + 1}</Link>
          </div>
        ))}
      </div>
    </div>
  );
}
