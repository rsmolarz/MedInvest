'use client';

import { useEffect } from 'react';
import type { SponsoredCreative } from '../../lib/adsClient';
import { adClickHref, logAdImpression } from '../../lib/adsClient';

type Props = {
  creative: SponsoredCreative;
  pageViewId?: string;
};

export default function SidebarSponsoredCard({ creative, pageViewId }: Props) {
  useEffect(() => {
    logAdImpression({ creativeId: creative.id, placement: 'sidebar', pageViewId }).catch(() => {});
  }, [creative.id, pageViewId]);

  return (
    <div className="rounded-xl border bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="text-xs text-slate-500">
          <span className="font-semibold">Sponsored</span>
        </div>
      </div>

      {creative.image_url ? (
        <img
          src={creative.image_url}
          alt="Sponsored"
          className="mt-2 h-32 w-full rounded-lg object-cover"
          loading="lazy"
        />
      ) : null}

      <div className="mt-2">
        <div className="text-sm font-semibold text-slate-900 leading-snug">
          {creative.headline}
        </div>
        <div className="mt-1 text-xs text-slate-600 line-clamp-3">
          {creative.body}
        </div>
      </div>

      <a
        href={adClickHref(creative.click_url)}
        className="mt-3 inline-flex w-full items-center justify-center rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-100"
      >
        {creative.cta_text}
      </a>

      {creative.disclaimer_text ? (
        <div className="mt-2 text-[10px] text-slate-500">
          {creative.disclaimer_text}
        </div>
      ) : null}
    </div>
  );
}
