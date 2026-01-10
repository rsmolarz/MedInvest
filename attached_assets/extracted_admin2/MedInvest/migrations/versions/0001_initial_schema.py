"""Initial schema.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-01-09

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("first_name", sa.String(length=50), nullable=False),
        sa.Column("last_name", sa.String(length=50), nullable=False),
        sa.Column("medical_license", sa.String(length=50), nullable=False),
        sa.Column("specialty", sa.String(length=100), nullable=False),
        sa.Column("npi_number", sa.String(length=20), nullable=True),
        sa.Column("license_state", sa.String(length=2), nullable=True),
        sa.Column("role", sa.String(length=30), nullable=True),
        sa.Column("verification_status", sa.String(length=30), nullable=True),
        sa.Column("verification_submitted_at", sa.DateTime(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("hospital_affiliation", sa.String(length=200), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("profile_image_url", sa.String(length=500), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("years_of_experience", sa.Integer(), nullable=True),
        sa.Column("investment_interests", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=True),
        sa.Column("account_active", sa.Boolean(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("totp_secret", sa.String(length=32), nullable=True),
        sa.Column("is_2fa_enabled", sa.Boolean(), nullable=True),
        sa.Column("password_reset_token", sa.String(length=100), nullable=True),
        sa.Column("password_reset_expires", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("medical_license", name="uq_users_medical_license"),
        sa.UniqueConstraint("npi_number", name="uq_users_npi_number"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_verification_status", "users", ["verification_status"], unique=False)

    # Core learning/content
    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("difficulty_level", sa.String(length=20), nullable=False),
        sa.Column("estimated_duration", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_modules_category", "modules", ["category"], unique=False)

    op.create_table(
        "user_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("modules.id"), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=True),
        sa.Column("completion_date", sa.DateTime(), nullable=True),
        sa.Column("time_spent", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_user_progress_user_id", "user_progress", ["user_id"], unique=False)
    op.create_index("ix_user_progress_module_id", "user_progress", ["module_id"], unique=False)

    op.create_table(
        "forum_topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_forum_topics_category", "forum_topics", ["category"], unique=False)

    op.create_table(
        "forum_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("forum_topics.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("forum_posts.id"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_forum_posts_topic_id", "forum_posts", ["topic_id"], unique=False)
    op.create_index("ix_forum_posts_user_id", "forum_posts", ["user_id"], unique=False)

    op.create_table(
        "portfolio_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("transaction_type", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("transaction_date", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_portfolio_transactions_user_id", "portfolio_transactions", ["user_id"], unique=False)
    op.create_index("ix_portfolio_transactions_symbol", "portfolio_transactions", ["symbol"], unique=False)

    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_resources_category", "resources", ["category"], unique=False)

    # Community/groups
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("privacy", sa.String(length=20), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name", name="uq_groups_name"),
    )
    op.create_index("ix_groups_privacy", "groups", ["privacy"], unique=False)

    # Social posts
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("post_type", sa.String(length=20), nullable=True),
        sa.Column("tags", sa.String(length=500), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_posts_created_at", "posts", ["created_at"], unique=False)
    op.create_index("ix_posts_group_id", "posts", ["group_id"], unique=False)
    op.create_index("ix_posts_author_id", "posts", ["author_id"], unique=False)

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("comments.id"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_comments_post_id", "comments", ["post_id"], unique=False)
    op.create_index("ix_comments_author_id", "comments", ["author_id"], unique=False)

    op.create_table(
        "likes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "post_id", name="unique_user_post_like"),
    )
    op.create_index("ix_likes_post_id", "likes", ["post_id"], unique=False)
    op.create_index("ix_likes_user_id", "likes", ["user_id"], unique=False)

    op.create_table(
        "follows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("follower_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("following_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("follower_id", "following_id", name="unique_follow_relationship"),
    )
    op.create_index("ix_follows_follower_id", "follows", ["follower_id"], unique=False)
    op.create_index("ix_follows_following_id", "follows", ["following_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("related_post_id", sa.Integer(), sa.ForeignKey("posts.id"), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"], unique=False)
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"], unique=False)
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"], unique=False)

    op.create_table(
        "group_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("group_id", "user_id", name="unique_group_membership"),
    )
    op.create_index("ix_group_memberships_group_id", "group_memberships", ["group_id"], unique=False)
    op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"], unique=False)

    op.create_table(
        "connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requester_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("addressee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("requester_id", "addressee_id", name="unique_connection_request"),
    )
    op.create_index("ix_connections_requester_id", "connections", ["requester_id"], unique=False)
    op.create_index("ix_connections_addressee_id", "connections", ["addressee_id"], unique=False)

    # Direct messaging
    op.create_table(
        "dm_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "dm_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("dm_threads.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("thread_id", "user_id", name="unique_dm_participant"),
    )
    op.create_index("ix_dm_participants_thread_id", "dm_participants", ["thread_id"], unique=False)
    op.create_index("ix_dm_participants_user_id", "dm_participants", ["user_id"], unique=False)

    op.create_table(
        "dm_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("dm_threads.id"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_dm_messages_thread_id", "dm_messages", ["thread_id"], unique=False)
    op.create_index("ix_dm_messages_created_at", "dm_messages", ["created_at"], unique=False)

    # Reputation
    op.create_table(
        "reputation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=True),
        sa.Column("related_post_id", sa.Integer(), sa.ForeignKey("posts.id"), nullable=True),
        sa.Column("related_group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_reputation_events_user_id", "reputation_events", ["user_id"], unique=False)
    op.create_index("ix_reputation_events_created_at", "reputation_events", ["created_at"], unique=False)


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("ix_reputation_events_created_at", table_name="reputation_events")
    op.drop_index("ix_reputation_events_user_id", table_name="reputation_events")
    op.drop_table("reputation_events")

    op.drop_index("ix_dm_messages_created_at", table_name="dm_messages")
    op.drop_index("ix_dm_messages_thread_id", table_name="dm_messages")
    op.drop_table("dm_messages")

    op.drop_index("ix_dm_participants_user_id", table_name="dm_participants")
    op.drop_index("ix_dm_participants_thread_id", table_name="dm_participants")
    op.drop_table("dm_participants")

    op.drop_table("dm_threads")

    op.drop_index("ix_connections_addressee_id", table_name="connections")
    op.drop_index("ix_connections_requester_id", table_name="connections")
    op.drop_table("connections")

    op.drop_index("ix_group_memberships_user_id", table_name="group_memberships")
    op.drop_index("ix_group_memberships_group_id", table_name="group_memberships")
    op.drop_table("group_memberships")

    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_is_read", table_name="notifications")
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_follows_following_id", table_name="follows")
    op.drop_index("ix_follows_follower_id", table_name="follows")
    op.drop_table("follows")

    op.drop_index("ix_likes_user_id", table_name="likes")
    op.drop_index("ix_likes_post_id", table_name="likes")
    op.drop_table("likes")

    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_index("ix_comments_post_id", table_name="comments")
    op.drop_table("comments")

    op.drop_index("ix_posts_author_id", table_name="posts")
    op.drop_index("ix_posts_group_id", table_name="posts")
    op.drop_index("ix_posts_created_at", table_name="posts")
    op.drop_table("posts")

    op.drop_index("ix_groups_privacy", table_name="groups")
    op.drop_table("groups")

    op.drop_index("ix_resources_category", table_name="resources")
    op.drop_table("resources")

    op.drop_index("ix_portfolio_transactions_symbol", table_name="portfolio_transactions")
    op.drop_index("ix_portfolio_transactions_user_id", table_name="portfolio_transactions")
    op.drop_table("portfolio_transactions")

    op.drop_index("ix_forum_posts_user_id", table_name="forum_posts")
    op.drop_index("ix_forum_posts_topic_id", table_name="forum_posts")
    op.drop_table("forum_posts")

    op.drop_index("ix_forum_topics_category", table_name="forum_topics")
    op.drop_table("forum_topics")

    op.drop_index("ix_user_progress_module_id", table_name="user_progress")
    op.drop_index("ix_user_progress_user_id", table_name="user_progress")
    op.drop_table("user_progress")

    op.drop_index("ix_modules_category", table_name="modules")
    op.drop_table("modules")

    op.drop_index("ix_users_verification_status", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
