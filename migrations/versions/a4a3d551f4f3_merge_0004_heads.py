"""merge_0004_heads

Revision ID: a4a3d551f4f3
Revises: 0004_deal_wizard_fields, 0004_invites_digests
Create Date: 2026-01-10 15:16:37.918722

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'a4a3d551f4f3'
down_revision = ('0004_deal_wizard_fields', '0004_invites_digests')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
