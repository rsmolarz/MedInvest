"""deal wizard fields

Revision ID: 0004_deal_wizard_fields
Revises: 0003_ai_jobs_idempotency
Create Date: 2026-01-10
"""

from alembic import op
import sqlalchemy as sa


revision = '0004_deal_wizard_fields'
down_revision = '0003_ai_jobs_idempotency'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('deal_details', sa.Column('feedback_areas', sa.String(length=200), nullable=True))
    op.add_column('deal_details', sa.Column('disclaimer_acknowledged', sa.Boolean(), nullable=True, server_default='false'))


def downgrade():
    op.drop_column('deal_details', 'disclaimer_acknowledged')
    op.drop_column('deal_details', 'feedback_areas')
