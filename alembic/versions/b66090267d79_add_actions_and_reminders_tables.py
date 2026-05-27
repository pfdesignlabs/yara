"""add actions and reminders tables

Revision ID: b66090267d79
Revises: bfba8268a85d
Create Date: 2026-05-27 13:36:58.215513
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b66090267d79"
down_revision = "bfba8268a85d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("urgency", sa.String(length=16), nullable=True),
        sa.Column("deadline_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'done', 'skipped')",
            name="ck_actions_status",
        ),
    )
    op.create_index(op.f("ix_actions_user_id"), "actions", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_actions_conversation_id"),
        "actions",
        ["conversation_id"],
        unique=False,
    )
    op.create_index("ix_actions_user_status", "actions", ["user_id", "status"], unique=False)
    op.create_index("ix_actions_source", "actions", ["source_type", "source_id"], unique=False)
    op.create_index(
        "ix_actions_open_deadline",
        "actions",
        ["deadline_date"],
        unique=False,
        postgresql_where=sa.text("status IN ('pending', 'in_progress')"),
    )

    op.create_table(
        "reminders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_message_id", sa.String(length=255), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'sent', 'cancelled')",
            name="ck_reminders_status",
        ),
    )
    op.create_index(op.f("ix_reminders_user_id"), "reminders", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_reminders_conversation_id"),
        "reminders",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_reminders_due",
        "reminders",
        ["scheduled_for"],
        unique=False,
        postgresql_where=sa.text("status = 'scheduled'"),
    )


def downgrade() -> None:
    op.drop_index("ix_reminders_due", table_name="reminders")
    op.drop_index(op.f("ix_reminders_conversation_id"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_user_id"), table_name="reminders")
    op.drop_table("reminders")

    op.drop_index("ix_actions_open_deadline", table_name="actions")
    op.drop_index("ix_actions_source", table_name="actions")
    op.drop_index("ix_actions_user_status", table_name="actions")
    op.drop_index(op.f("ix_actions_conversation_id"), table_name="actions")
    op.drop_index(op.f("ix_actions_user_id"), table_name="actions")
    op.drop_table("actions")
