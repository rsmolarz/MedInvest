"""Deal schema, AI jobs, and reputation score.

Revision ID: 0002_deals_ai_reputation
Revises: 0001_initial_schema
Create Date: 2026-01-09

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_deals_ai_reputation"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cached reputation score on users
    op.add_column("users", sa.Column("reputation_score", sa.Integer(), nullable=True, server_default="0"))

    # Deal details (one-to-one w/ posts)
    op.create_table(
        "deal_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("asset_class", sa.String(length=60), nullable=False),
        sa.Column("strategy", sa.String(length=60), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("time_horizon_months", sa.Integer(), nullable=True),
        sa.Column("target_irr", sa.Float(), nullable=True),
        sa.Column("target_multiple", sa.Float(), nullable=True),
        sa.Column("minimum_investment", sa.Integer(), nullable=True),
        sa.Column("sponsor_name", sa.String(length=120), nullable=True),
        sa.Column("sponsor_track_record", sa.Text(), nullable=True),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("key_risks", sa.Text(), nullable=True),
        sa.Column("diligence_needed", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("post_id", name="uq_deal_details_post_id"),
    )
    op.create_index("ix_deal_details_asset_class", "deal_details", ["asset_class"], unique=False)
    op.create_index("ix_deal_details_status", "deal_details", ["status"], unique=False)

    # Deal analyses (persisted snapshots)
    op.create_table(
        "deal_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deal_details.id"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_deal_analyses_deal_id", "deal_analyses", ["deal_id"], unique=False)

    # AI jobs queue
    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id"), nullable=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deal_details.id"), nullable=True),
        sa.Column("input_text", sa.Text(), nullable=True),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ai_jobs_status", "ai_jobs", ["status", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_jobs_status", table_name="ai_jobs")
    op.drop_table("ai_jobs")
    op.drop_index("ix_deal_analyses_deal_id", table_name="deal_analyses")
    op.drop_table("deal_analyses")
    op.drop_index("ix_deal_details_status", table_name="deal_details")
    op.drop_index("ix_deal_details_asset_class", table_name="deal_details")
    op.drop_table("deal_details")
    op.drop_column("users", "reputation_score")
