export type AdPlacement = 'feed' | 'sidebar' | 'deal_inline';

export type SponsoredCreative = {
  id: number;
  format: AdPlacement;
  headline: string;
  body: string;
  image_url?: string | null;
  cta_text: string;
  disclaimer_text?: string;
  click_url: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';

export async function fetchAd(params: {
  placement: AdPlacement;
  keywords?: string;
  specialty?: string;
  role?: string;
  state?: string;
}): Promise<SponsoredCreative | null> {
  const sp = new URLSearchParams({ placement: params.placement });
  if (params.keywords) sp.set('keywords', params.keywords);
  if (params.specialty) sp.set('specialty', params.specialty);
  if (params.role) sp.set('role', params.role);
  if (params.state) sp.set('state', params.state);

  const res = await fetch(`${API_BASE}/ads/serve?${sp.toString()}`, {
    credentials: 'include',
    cache: 'no-store',
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data?.creative || null;
}

export async function logAdImpression(params: {
  creativeId: number;
  placement: AdPlacement;
  pageViewId?: string;
}) {
  await fetch(`${API_BASE}/ads/impression`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      creative_id: params.creativeId,
      placement: params.placement,
      page_view_id: params.pageViewId || null,
    }),
  });
}

export function adClickHref(clickUrl: string) {
  // clickUrl is returned as a relative path from the API, e.g. /ads/click/{token}
  if (clickUrl.startsWith('http')) return clickUrl;
  return `${API_BASE}${clickUrl}`;
}
