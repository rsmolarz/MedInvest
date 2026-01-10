# MedInvest Ads: UI + API starter kit

This kit adds **internal ad serving** (sponsored cards) with:

- Verified-user ad delivery (`GET /ads/serve`)
- Impression logging with idempotency (`POST /ads/impression`)
- Click logging via signed redirect (`GET /ads/click/{token}`)
- Admin CRUD for advertisers/campaigns/creatives (minimal)
- Next.js components for **feed** and **sidebar** placements

## Quick start

### Backend
1. Ensure the FastAPI app includes the ads router:
   - `app/main.py` includes `app.include_router(ads.router, prefix="/ads")`
2. Start the API and create records:
   - POST `/ads/admin/advertisers`
   - POST `/ads/admin/campaigns`
   - POST `/ads/admin/creatives`

### Frontend
Set an API base URL (if different origin):

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Example usage:

```tsx
import { useEffect, useState } from 'react';
import { fetchAd } from '@/lib/adsClient';
import FeedSponsoredCard from '@/components/ads/FeedSponsoredCard';

export default function DealsFeed() {
  const [ad, setAd] = useState(null);
  useEffect(() => {
    fetchAd({ placement: 'feed', keywords: 'self-storage ASC' }).then(setAd);
  }, []);

  return (
    <div className="space-y-4">
      {/* ... normal feed cards ... */}
      {ad ? <FeedSponsoredCard creative={ad} pageViewId="pv_123" /> : null}
    </div>
  );
}
```

## Targeting JSON
Campaign `targeting_json` supports:

```json
{
  "specialty": ["ENT"],
  "role": ["attending"],
  "state": ["TX"],
  "placement": ["feed", "sidebar"],
  "keywords_any": ["ASC", "self-storage"],
  "exclude_user_ids": [1, 2]
}
```

## Notes
- This is an internal MVP ad server. Frequency caps, pacing, and MRC/IAB-grade auditing can be layered next.
- For regulated categories, always populate `disclaimer_text`.
