"""ops/analytics/moderation/outcomes/sponsors

Revision ID: 0005_ops_analytics_moderation_outcomes_sponsors
Revises: 0004_invites_digests
Create Date: 2026-01-10
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005_ops_analytics_moderation_outcomes_sponsors'
down_revision = '0004_invites_digests'
branch_labels = None
depends_on = None


def upgrade():
    # User additions
    with op.batch_alter_table('user') as batch_op:
        batch_op.add_column(sa.Column('can_review_verifications', sa.Boolean(), server_default=sa.text('0'), nullable=False))

    # Analytics / activity
    op.create_table(
        'user_activity',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('activity_type', sa.String(length=80), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_user_activity_user_created', 'user_activity', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_user_activity_created', 'user_activity', ['created_at'], unique=False)
    op.create_index('ix_user_activity_type_created', 'user_activity', ['activity_type', 'created_at'], unique=False)

    # Alerts
    op.create_table(
        'alert',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('alert_type', sa.String(length=80), nullable=False),
        sa.Column('severity', sa.String(length=20), server_default='warning', nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='open', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_alert_type_status_created', 'alert', ['alert_type', 'status', 'created_at'], unique=False)

    # Verification queue
    op.create_table(
        'verification_queue_entry',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('assigned_reviewer_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_verif_queue_status_created', 'verification_queue_entry', ['status', 'created_at'], unique=False)

    # Onboarding prompts
    op.create_table(
        'onboarding_prompt',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('prompt_key', sa.String(length=50), nullable=False),
        sa.Column('cohort_dimension', sa.String(length=50), nullable=True),
        sa.Column('cohort_value', sa.String(length=120), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('cta_text', sa.String(length=120), nullable=True),
        sa.Column('cta_href', sa.String(length=240), nullable=True),
        sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_onboarding_prompt_key', 'onboarding_prompt', ['prompt_key'], unique=True)

    op.create_table(
        'user_prompt_dismissal',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('prompt_id', sa.Integer(), sa.ForeignKey('onboarding_prompt.id'), nullable=False),
        sa.Column('dismissed_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_user_prompt_dismissal_user_prompt', 'user_prompt_dismissal', ['user_id', 'prompt_id'], unique=True)

    # Invite credit events
    op.create_table(
        'invite_credit_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('delta', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_invite_credit_event_user_created', 'invite_credit_event', ['user_id', 'created_at'], unique=False)

    # Cohort norms
    op.create_table(
        'cohort_norm',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('dimension', sa.String(length=50), nullable=False),
        sa.Column('value', sa.String(length=120), nullable=False),
        sa.Column('max_reports_before_hide', sa.Integer(), server_default='3', nullable=False),
        sa.Column('max_reports_before_lock', sa.Integer(), server_default='6', nullable=False),
        sa.Column('min_rep_to_bypass', sa.Integer(), server_default='80', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_cohort_norm_dim_value', 'cohort_norm', ['dimension', 'value'], unique=True)

    # Moderation
    op.create_table(
        'moderation_event',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
    )
    op.create_index('ix_moderation_entity', 'moderation_event', ['entity_type', 'entity_id', 'created_at'], unique=False)

    op.create_table(
        'content_report',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('reporter_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('reason', sa.String(length=120), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='open', nullable=False),
        sa.Column('resolution', sa.String(length=40), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
    )
    op.create_index('ix_content_report_entity', 'content_report', ['entity_type', 'entity_id', 'created_at'], unique=False)
    op.create_index('ix_content_report_status', 'content_report', ['status', 'created_at'], unique=False)

    # Deal outcomes
    op.create_table(
        'deal_outcome',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('deal_id', sa.Integer(), sa.ForeignKey('deal_details.id'), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('invested', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('committed_amount', sa.Integer(), nullable=True),
        sa.Column('realized_irr', sa.Float(), nullable=True),
        sa.Column('realized_multiple', sa.Float(), nullable=True),
        sa.Column('writeup', sa.Text(), nullable=True),
        sa.Column('lessons_learned', sa.Text(), nullable=True),
        sa.Column('red_flags_missed', sa.Text(), nullable=True),
        sa.Column('what_went_right', sa.Text(), nullable=True),
        sa.Column('what_went_wrong', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_deal_outcome_deal_created', 'deal_outcome', ['deal_id', 'created_at'], unique=False)

    # Sponsor profiles + reviews
    op.create_table(
        'sponsor_profile',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('firm_name', sa.String(length=200), nullable=True),
        sa.Column('website', sa.String(length=200), nullable=True),
        sa.Column('aum_estimate', sa.String(length=100), nullable=True),
        sa.Column('deal_count', sa.Integer(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('track_record_summary', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('verified_by_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_sponsor_profile_user', 'sponsor_profile', ['user_id'], unique=True)
    op.create_index('ix_sponsor_profile_status', 'sponsor_profile', ['status', 'created_at'], unique=False)

    op.create_table(
        'sponsor_review',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sponsor_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('reviewer_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('deal_id', sa.Integer(), sa.ForeignKey('deal_details.id'), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('review_body', sa.Text(), nullable=True),
        sa.Column('is_anonymous', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_sponsor_review_sponsor_created', 'sponsor_review', ['sponsor_user_id', 'created_at'], unique=False)


def downgrade():
    op.drop_table('sponsor_review')
    op.drop_table('sponsor_profile')
    op.drop_table('deal_outcome')
    op.drop_table('content_report')
    op.drop_table('moderation_event')
    op.drop_table('cohort_norm')
    op.drop_table('invite_credit_event')
    op.drop_table('user_prompt_dismissal')
    op.drop_table('onboarding_prompt')
    op.drop_table('verification_queue_entry')
    op.drop_table('alert')
    op.drop_table('user_activity')
    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_column('can_review_verifications')
