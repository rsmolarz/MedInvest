from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from app import app, db
from models import AiJob, DealAnalysis, DealDetails, Post
from ai_service import summarize_text, analyze_deal


def enqueue_ai_job(
    *,
    job_type: str,
    created_by_id: int,
    input_text: Optional[str] = None,
    post_id: Optional[int] = None,
    deal_id: Optional[int] = None,
) -> AiJob:
    job = AiJob(
        job_type=job_type,
        created_by_id=created_by_id,
        input_text=(input_text or None),
        post_id=post_id,
        deal_id=deal_id,
        status="queued",
    )
    db.session.add(job)
    db.session.commit()
    return job


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
                result = analyze_deal(text)
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
