"""Add AIAuditLog table

Revision ID: add_ai_audit_log
Revises: 
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_ai_audit_log'
down_revision = 'a4a3d551f4f3'
branch_labels = None
depends_on = None

def upgrade():
    # Check if table already exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'ai_audit_logs' not in inspector.get_table_names():
        op.create_table('ai_audit_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('timestamp', sa.DateTime(), nullable=True),
            sa.Column('provider', sa.String(50), nullable=True),
            sa.Column('model', sa.String(100), nullable=True),
            sa.Column('prompt_hash', sa.String(64), nullable=True),
            sa.Column('prompt_preview', sa.Text(), nullable=True),
            sa.Column('tokens_used', sa.Integer(), nullable=True),
            sa.Column('latency_ms', sa.Integer(), nullable=True),
            sa.Column('success', sa.Boolean(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('feature', sa.String(100), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('idx_ai_audit_timestamp', 'ai_audit_logs', ['timestamp'])
        op.create_index('idx_ai_audit_provider', 'ai_audit_logs', ['provider'])

def downgrade():
    op.drop_index('idx_ai_audit_provider', table_name='ai_audit_logs')
    op.drop_index('idx_ai_audit_timestamp', table_name='ai_audit_logs')
    op.drop_table('ai_audit_logs')
