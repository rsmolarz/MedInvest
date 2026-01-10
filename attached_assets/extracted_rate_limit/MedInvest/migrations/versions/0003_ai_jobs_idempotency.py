"""ai jobs idempotency

Revision ID: 0003_ai_jobs_idempotency
Revises: 0002_deals_ai_reputation
Create Date: 2026-01-10
"""

from alembic import op
import sqlalchemy as sa


revision = '0003_ai_jobs_idempotency'
down_revision = '0002_deals_ai_reputation'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ai_jobs', sa.Column('idempotency_key', sa.String(length=120), nullable=True))
    op.add_column('ai_jobs', sa.Column('request_fingerprint', sa.String(length=64), nullable=True))
    op.create_index('ix_ai_jobs_request_fingerprint', 'ai_jobs', ['request_fingerprint'])
    op.create_index('ix_ai_jobs_creator_type_fingerprint', 'ai_jobs', ['created_by_id', 'job_type', 'request_fingerprint'])


def downgrade():
    op.drop_index('ix_ai_jobs_creator_type_fingerprint', table_name='ai_jobs')
    op.drop_index('ix_ai_jobs_request_fingerprint', table_name='ai_jobs')
    op.drop_column('ai_jobs', 'request_fingerprint')
    op.drop_column('ai_jobs', 'idempotency_key')
