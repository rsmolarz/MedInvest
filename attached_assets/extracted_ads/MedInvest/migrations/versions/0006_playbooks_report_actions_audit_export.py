"""playbooks + report action history

Revision ID: 0006_playbooks_report_actions
Revises: 0005_ops_analytics_moderation_outcomes_sponsors
Create Date: 2026-01-10

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_playbooks_report_actions'
down_revision = '0005_ops_analytics_moderation_outcomes_sponsors'
branch_labels = None
depends_on = None


def upgrade():
    # --- report_actions (admin notes + audit trail)
    op.create_table(
        'report_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('report_id', sa.Integer(), sa.ForeignKey('content_report.id', ondelete='CASCADE'), nullable=False),
        sa.Column('admin_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_report_actions_report_id', 'report_actions', ['report_id'])
    op.create_index('ix_report_actions_admin_user_id', 'report_actions', ['admin_user_id'])
    op.create_index('ix_report_actions_action', 'report_actions', ['action'])
    op.create_index('ix_report_actions_created_at', 'report_actions', ['created_at'])

    # --- cohort_playbooks (moderator playbooks by cohort)
    op.create_table(
        'cohort_playbooks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cohort_dimension', sa.String(length=20), nullable=False),
        sa.Column('cohort_value', sa.String(length=120), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('guidelines', sa.Text(), nullable=False),
        sa.Column('escalation_steps', sa.Text(), nullable=True),
        sa.Column('examples_allowed', sa.Text(), nullable=True),
        sa.Column('examples_disallowed', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('cohort_dimension', 'cohort_value', name='uq_cohort_playbook'),
    )
    op.create_index('ix_cohort_playbooks_dimension', 'cohort_playbooks', ['cohort_dimension'])
    op.create_index('ix_cohort_playbooks_value', 'cohort_playbooks', ['cohort_value'])
    op.create_index('ix_cohort_playbooks_updated_at', 'cohort_playbooks', ['updated_at'])


def downgrade():
    op.drop_index('ix_cohort_playbooks_updated_at', table_name='cohort_playbooks')
    op.drop_index('ix_cohort_playbooks_value', table_name='cohort_playbooks')
    op.drop_index('ix_cohort_playbooks_dimension', table_name='cohort_playbooks')
    op.drop_table('cohort_playbooks')

    op.drop_index('ix_report_actions_created_at', table_name='report_actions')
    op.drop_index('ix_report_actions_action', table_name='report_actions')
    op.drop_index('ix_report_actions_admin_user_id', table_name='report_actions')
    op.drop_index('ix_report_actions_report_id', table_name='report_actions')
    op.drop_table('report_actions')
