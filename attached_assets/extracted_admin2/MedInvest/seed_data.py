"""Seed minimal data for MLP.

Usage:
  flask --app app.py shell
  >>> from seed_data import seed_defaults; seed_defaults()

Or run:
  python -c "from seed_data import seed_defaults; seed_defaults()"

This is idempotent.
"""

from __future__ import annotations

from app import app, db
from models import OnboardingPrompt, CohortNorm


def seed_defaults() -> dict:
    created = 0
    with app.app_context():
        # Global onboarding prompt: first deal wizard
        existing = OnboardingPrompt.query.filter_by(prompt_key='first_deal_wizard').first()
        if not existing:
            db.session.add(OnboardingPrompt(
                prompt_key='first_deal_wizard',
                title='Post your first deal',
                body='Use the First-Deal Wizard to share a deal, auto-run the AI analyst, and get peer feedback.',
                cta_text='Start First-Deal Wizard',
                cta_href='/deals/new?auto_analyze=1',
                cohort_dimension='*',
                cohort_value='*',
                priority=100,
                is_active=True,
            ))
            created += 1

        # Default cohort norms
        norm = CohortNorm.query.filter_by(cohort_dimension='*', cohort_value='*').first()
        if not norm:
            db.session.add(CohortNorm(
                cohort_dimension='*',
                cohort_value='*',
                max_reports_before_hide=3,
                max_reports_before_lock=6,
                min_reputation_to_post=-999,
                min_reputation_to_comment=-999,
            ))
            created += 1

        db.session.commit()
    return {'created': created}
