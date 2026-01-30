"""Add DoctorInvite table and must_change_password field

Revision ID: add_doctor_invite
Revises: add_ai_audit_log
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_doctor_invite'
down_revision = 'add_ai_audit_log'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Add must_change_password to users table
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'must_change_password' not in columns:
        op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=True, server_default='false'))
    
    # Create doctor_invites table
    if 'doctor_invites' not in inspector.get_table_names():
        op.create_table('doctor_invites',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('token', sa.String(64), nullable=False),
            sa.Column('email', sa.String(120), nullable=False),
            sa.Column('first_name', sa.String(50), nullable=True),
            sa.Column('last_name', sa.String(50), nullable=True),
            sa.Column('specialty', sa.String(100), nullable=True),
            sa.Column('temp_password', sa.String(20), nullable=True),
            sa.Column('status', sa.String(20), nullable=True),
            sa.Column('created_by_id', sa.Integer(), nullable=False),
            sa.Column('accepted_by_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('accepted_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
            sa.ForeignKeyConstraint(['accepted_by_id'], ['users.id'])
        )
        op.create_index('idx_doctor_invites_token', 'doctor_invites', ['token'], unique=True)
        op.create_index('idx_doctor_invites_status', 'doctor_invites', ['status'])

def downgrade():
    op.drop_index('idx_doctor_invites_status', table_name='doctor_invites')
    op.drop_index('idx_doctor_invites_token', table_name='doctor_invites')
    op.drop_table('doctor_invites')
    op.drop_column('users', 'must_change_password')
