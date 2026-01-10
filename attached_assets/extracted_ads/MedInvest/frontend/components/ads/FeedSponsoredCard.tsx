'use client';

import { useEffect } from 'react';
import type { SponsoredCreative } from '../../lib/adsClient';
import { adClickHref, logAdImpression } from '../../lib/adsClient';

type Props = {
  creative: SponsoredCreative;
  pageViewId?: string;
};

export default function FeedSponsoredCard({ creative, pageViewId }: Props) {
  useEffect(() => {
    logAdImpression({ creativeId: creative.id, placement: 'feed', pageViewId }).catch(() => {});
  }, [creative.id, pageViewId]);

  return (
    <div className="rounded-xl border bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <span className="font-semibold">Sponsored</span>
        <span className="rounded-full bg-blue-50 px-2 py-0.5 font-medium text-blue-700">
          {creative.format === 'feed' ? 'Feed' : creative.format}
        </span>
      </div>

      <div className="mt-3 flex gap-4">
        {creative.image_url ? (
          <img
            src={creative.image_url}
            alt="Sponsored"
            className="h-20 w-20 flex-none rounded-lg object-cover"
            loading="lazy"
          />
        ) : null}

        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-semibold text-slate-900 leading-snug">
            {creative.headline}
          </h3>
          <p className="mt-1 text-sm text-slate-600 line-clamp-2">{creative.body}</p>

          <div className="mt-3 flex items-center justify-between gap-3">
            <a
              href={adClickHref(creative.click_url)}
              className="inline-flex items-center justify-center rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            >
              {creative.cta_text}
            </a>
            <span className="text-[11px] text-slate-400">Sponsor disclosure</span>
          </div>
        </div>
      </div>

      {creative.disclaimer_text ? (
        <div className="mt-3 text-[11px] text-slate-500">
          {creative.disclaimer_text}
        </div>
      ) : null}
    </div>
  );
}
