"""Deal Memory Engine

Surfaces lessons from prior closed/passed deals similar to the current one.
This is intentionally lightweight (no embeddings required) to ship quickly.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional

from models import DealDetails, DealOutcome, Post


def find_similar_deal_outcomes(deal_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    deal = DealDetails.query.get(deal_id)
    if not deal:
        return []

    # Primary similarity: same asset class (fast + usually correct).
    q = (
        DealOutcome.query
        .join(DealDetails, DealOutcome.deal_id == DealDetails.id)
        .filter(DealDetails.id != deal.id)
        .filter(DealDetails.asset_class == deal.asset_class)
        .order_by(DealOutcome.created_at.desc())
        .limit(max(1, min(int(limit), 20)))
    )

    items: List[Dict[str, Any]] = []
    for o in q.all():
        d = DealDetails.query.get(o.deal_id)
        p = Post.query.get(d.post_id) if d else None
        items.append({
            "deal_id": d.id if d else None,
            "post_id": d.post_id if d else None,
            "title": (p.title if p else None) or f"Deal #{d.id}" if d else None,
            "asset_class": d.asset_class if d else None,
            "strategy": d.strategy if d else None,
            "location": d.location if d else None,
            "outcome": o.outcome,
            "key_lessons": o.key_lessons,
            "what_went_right": o.what_went_right,
            "what_went_wrong": o.what_went_wrong,
            "created_at": o.created_at.isoformat() + "Z" if o.created_at else None,
        })
    return items


def memory_context_text(deal_id: int, limit: int = 5) -> str:
    """Render similar outcomes into a compact text block for AI context."""
    sims = find_similar_deal_outcomes(deal_id=deal_id, limit=limit)
    if not sims:
        return ""

    lines: List[str] = ["Similar closed/passed deals and lessons:"]
    for i, s in enumerate(sims, start=1):
        title = s.get("title") or "(untitled)"
        outcome = s.get("outcome") or "unknown"
        lessons = (s.get("key_lessons") or "").strip()
        if len(lessons) > 400:
            lessons = lessons[:400] + "..."
        lines.append(f"{i}. {title} — outcome: {outcome}. Lessons: {lessons}")
    return "\n".join(lines)
