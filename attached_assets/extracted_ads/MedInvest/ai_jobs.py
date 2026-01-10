from __future__ import annotations

import json
import hashlib
from datetime import datetime
from typing import Optional

from app import app, db
from models import AiJob, DealAnalysis, DealDetails, Post, Notification
from ai_service import summarize_text, analyze_deal, analyze_deal_with_memory
from deal_memory import memory_context_text


AI_RATE_LIMIT_WINDOW_SECONDS = 60 * 60  # 1 hour
AI_RATE_LIMIT_MAX_JOBS_PER_WINDOW = 12


def _fingerprint(
    *, job_type: str, created_by_id: int, post_id: Optional[int], deal_id: Optional[int], input_text: Optional[str]
) -> str:
    """Stable fingerprint for de-duplication."""
    payload = {
        "job_type": job_type,
        "created_by_id": created_by_id,
        "post_id": post_id,
        "deal_id": deal_id,
        "input_text": (input_text or "")[:4000],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _check_rate_limit(created_by_id: int) -> None:
    """DB-based rate limit. Raises ValueError if exceeded."""
    cutoff = datetime.utcnow().timestamp() - AI_RATE_LIMIT_WINDOW_SECONDS
    # created_at is datetime; compare via Python by filtering with datetime
    from datetime import datetime as _dt

    cutoff_dt = _dt.utcfromtimestamp(cutoff)
    recent_count = (
        AiJob.query.filter(AiJob.created_by_id == created_by_id)
        .filter(AiJob.created_at >= cutoff_dt)
        .count()
    )
    if recent_count >= AI_RATE_LIMIT_MAX_JOBS_PER_WINDOW:
        raise ValueError("rate_limited")


def enqueue_ai_job(
    *,
    job_type: str,
    created_by_id: int,
    input_text: Optional[str] = None,
    post_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> AiJob:
    """Enqueue a job with idempotency + rate limiting.

    - If an idempotency_key is supplied, return existing queued/running job for that key.
    - If an identical fingerprint is already queued/running (same user+job_type+inputs), reuse it.
    - Enforces a simple per-user DB rate limit.
    """

    _check_rate_limit(created_by_id)

    fp = _fingerprint(
        job_type=job_type,
        created_by_id=created_by_id,
        post_id=post_id,
        deal_id=deal_id,
        input_text=input_text,
    )

    # Strict idempotency by key (if provided)
    if idempotency_key:
        existing = (
            AiJob.query.filter_by(created_by_id=created_by_id, job_type=job_type, idempotency_key=idempotency_key)
            .filter(AiJob.status.in_(["queued", "running"]))
            .order_by(AiJob.created_at.desc())
            .first()
        )
        if existing:
            setattr(existing, "_reused", True)
            return existing

    # Best-effort de-dupe by fingerprint
    existing_fp = (
        AiJob.query.filter_by(created_by_id=created_by_id, job_type=job_type, request_fingerprint=fp)
        .filter(AiJob.status.in_(["queued", "running"]))
        .order_by(AiJob.created_at.desc())
        .first()
    )
    if existing_fp:
        setattr(existing_fp, "_reused", True)
        return existing_fp

    job = AiJob(
        job_type=job_type,
        created_by_id=created_by_id,
        input_text=(input_text or None),
        post_id=post_id,
        deal_id=deal_id,
        status="queued",
        idempotency_key=idempotency_key,
        request_fingerprint=fp,
    )
    db.session.add(job)
    db.session.commit()
    return job


def _notify_ai_complete(job: AiJob) -> None:
    """Create notification events when AI job completes."""
    try:
        # Always notify the requestor
        msg = "AI analysis complete" if job.job_type == "analyze_deal" else "AI summary complete"
        related_post_id = None
        if job.deal_id:
            deal = DealDetails.query.get(job.deal_id)
            related_post_id = deal.post_id if deal else None
        elif job.post_id:
            related_post_id = job.post_id

        n1 = Notification(
            recipient_id=job.created_by_id,
            sender_id=None,
            notification_type="ai_complete",
            message=msg,
            related_post_id=related_post_id,
            is_read=False,
        )
        db.session.add(n1)

        # Also notify the deal/post author if different
        if related_post_id:
            post = Post.query.get(related_post_id)
            if post and post.author_id and post.author_id != job.created_by_id:
                n2 = Notification(
                    recipient_id=post.author_id,
                    sender_id=None,
                    notification_type="ai_complete",
                    message=msg + " (requested by another physician)",
                    related_post_id=related_post_id,
                    is_read=False,
                )
                db.session.add(n2)
    except Exception:
        # Never fail the job on notification issues
        return


def _job_input_text(job: AiJob) -> str:
    if job.input_text:
        return job.input_text

    # Derive from post / deal if present
    if job.deal_id:
        deal: DealDetails | None = DealDetails.query.get(job.deal_id)
        if not deal:
            return ""
        post = Post.query.get(deal.post_id) if deal.post_id else None
        parts = [
            f"ASSET_CLASS: {deal.asset_class}",
            f"STRATEGY: {deal.strategy or ''}",
            f"LOCATION: {deal.location or ''}",
            f"HORIZON_MONTHS: {deal.time_horizon_months or ''}",
            f"TARGET_IRR: {deal.target_irr or ''}",
            f"TARGET_MULTIPLE: {deal.target_multiple or ''}",
            f"MINIMUM_INVESTMENT: {deal.minimum_investment or ''}",
            f"SPONSOR: {deal.sponsor_name or ''}",
            "THESIS:\n" + (deal.thesis or ""),
        ]
        if post and post.content:
            parts.append("POST_CONTENT:\n" + post.content)
        if deal.key_risks:
            parts.append("KEY_RISKS:\n" + deal.key_risks)
        if deal.diligence_needed:
            parts.append("DILIGENCE_NEEDED:\n" + deal.diligence_needed)
        return "\n\n".join(parts).strip()

    if job.post_id:
        post = Post.query.get(job.post_id)
        return (post.content or "").strip() if post else ""

    return ""


def process_job(job_id: int) -> AiJob:
    """Execute a job synchronously (used by worker)."""
    with app.app_context():
        job: AiJob | None = AiJob.query.get(job_id)
        if not job:
            raise ValueError("job not found")

        if job.status not in ("queued", "running"):
            return job

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.session.add(job)
        db.session.commit()

        try:
            text = _job_input_text(job)
            if not text:
                raise ValueError("missing input_text")

            if job.job_type == "summarize_thread":
                result = summarize_text(text)
                job.output_text = result.get("summary")
                job.output_json = json.dumps(result)

            elif job.job_type == "analyze_deal":
                mem = ""
                try:
                    if job.deal_id:
                        mem = memory_context_text(job.deal_id, limit=5)
                except Exception:
                    mem = ""
                result = analyze_deal_with_memory(text, mem)
                job.output_text = result.get("analysis")
                job.output_json = json.dumps(result)

                if job.deal_id and job.output_text:
                    # Persist as an analysis snapshot tied to the deal
                    analysis = DealAnalysis(
                        deal_id=job.deal_id,
                        created_by_id=job.created_by_id,
                        provider=result.get("provider") or "openai",
                        model=result.get("model"),
                        output_text=job.output_text,
                        output_json=job.output_json,
                    )
                    db.session.add(analysis)

            else:
                raise ValueError(f"unknown job_type: {job.job_type}")

            job.status = "done"
            job.finished_at = datetime.utcnow()
            db.session.add(job)
            _notify_ai_complete(job)
            db.session.commit()
            return job
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.finished_at = datetime.utcnow()
            db.session.add(job)
            db.session.commit()
            return job


def claim_next_job() -> Optional[AiJob]:
    """Claim the next queued job. Simple DB-queue semantics."""
    with app.app_context():
        job = (
            AiJob.query.filter_by(status="queued")
            .order_by(AiJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if not job:
            return None
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.session.add(job)
        db.session.commit()
        return job
