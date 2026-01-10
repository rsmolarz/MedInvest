"""invites and weekly digests

Revision ID: 0004_invites_digests
Revises: 0003_ai_jobs_idempotency
Create Date: 2026-01-10
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_invites_digests'
down_revision = '0003_ai_jobs_idempotency'
branch_labels = None
depends_on = None


def upgrade():
    # invites
    op.create_table(
        'invites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('inviter_user_id', sa.Integer(), nullable=False),
        sa.Column('invitee_email', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='issued'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['inviter_user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_invites_code', 'invites', ['code'], unique=True)
    op.create_index('ix_invites_inviter_user_id', 'invites', ['inviter_user_id'])
    op.create_index('ix_invites_status', 'invites', ['status'])
    op.create_index('ix_invites_expires_at', 'invites', ['expires_at'])

    # users: invite_credits + invite_id
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('invite_credits', sa.Integer(), nullable=True, server_default='2'))
        batch.add_column(sa.Column('invite_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_users_invite_id', 'invites', ['invite_id'], ['id'])
        batch.create_index('ix_users_reputation_score', ['reputation_score'])
        batch.create_index('ix_users_invite_id', ['invite_id'])

    # digests
    op.create_table(
        'digests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_digests_period_start', 'digests', ['period_start'])
    op.create_index('ix_digests_period_end', 'digests', ['period_end'])
    op.create_index('ix_digests_created_at', 'digests', ['created_at'])

    op.create_table(
        'digest_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('digest_id', sa.Integer(), nullable=False),
        sa.Column('item_type', sa.String(length=20), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['digest_id'], ['digests.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_digest_items_digest_id', 'digest_items', ['digest_id'])
    op.create_index('ix_digest_items_item_type', 'digest_items', ['item_type'])
    op.create_index('ix_digest_items_created_at', 'digest_items', ['created_at'])


def downgrade():
    op.drop_index('ix_digest_items_created_at', table_name='digest_items')
    op.drop_index('ix_digest_items_item_type', table_name='digest_items')
    op.drop_index('ix_digest_items_digest_id', table_name='digest_items')
    op.drop_table('digest_items')

    op.drop_index('ix_digests_created_at', table_name='digests')
    op.drop_index('ix_digests_period_end', table_name='digests')
    op.drop_index('ix_digests_period_start', table_name='digests')
    op.drop_table('digests')

    with op.batch_alter_table('users') as batch:
        batch.drop_index('ix_users_invite_id')
        batch.drop_index('ix_users_reputation_score')
        batch.drop_constraint('fk_users_invite_id', type_='foreignkey')
        batch.drop_column('invite_id')
        batch.drop_column('invite_credits')

    op.drop_index('ix_invites_expires_at', table_name='invites')
    op.drop_index('ix_invites_status', table_name='invites')
    op.drop_index('ix_invites_inviter_user_id', table_name='invites')
    op.drop_index('ix_invites_code', table_name='invites')
    op.drop_table('invites')
