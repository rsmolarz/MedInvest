'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import Link from 'next/link';

export default function DigestDetailPage({ params }: { params: { digestId: string } }) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setErr(null);
    const res = await apiFetch(`/api/digests/${params.digestId}`);
    if (!res.ok) {
      setErr('Failed to load digest');
      return;
    }
    const j = await res.json();
    setData(j);
  }

  useEffect(() => { load(); }, [params.digestId]);

  if (err) return <div style={{ color: 'tomato' }}>{err}</div>;
  if (!data) return <div>Loading…</div>;

  const items = data.items || [];
  const deals = items.filter((i: any) => i.item_type === 'deal');
  const comments = items.filter((i: any) => i.item_type === 'comment');
  const summary = items.find((i: any) => i.item_type === 'summary')?.payload?.summary;

  return (
    <div>
      <h1>Digest</h1>
      {summary && <div style={{ marginTop: 8, opacity: 0.9 }}>{summary}</div>}

      <h2 style={{ marginTop: 18 }}>Top Deals</h2>
      {deals.map((d: any) => (
        <div key={d.id} style={{ marginTop: 6 }}>
          <Link href={`/deals/${d.entity_id}`}>Deal #{d.rank}</Link> <span style={{ opacity: 0.8 }}>({Number(d.score || 0).toFixed(2)})</span>
        </div>
      ))}

      <h2 style={{ marginTop: 18 }}>Top Comments</h2>
      {comments.map((c: any) => (
        <div key={c.id} style={{ marginTop: 6 }}>
          Comment #{c.rank} <span style={{ opacity: 0.8 }}>({Number(c.score || 0).toFixed(2)})</span>
        </div>
      ))}
    </div>
  );
}
