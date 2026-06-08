"""add conversation sessions table

Revision ID: a1b2c3d4e5f6
Revises: 2c9f1a4f9c11
Create Date: 2026-06-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "2c9f1a4f9c11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
        sa.Column("session_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_uuid", sa.UUID(), nullable=False),
        sa.Column("session_key", sa.String(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("current_crop", sa.String(), nullable=True),
        sa.Column("growth_stage", sa.String(), nullable=True),
        sa.Column("last_topic", sa.String(), nullable=True),
        sa.Column("last_problem", sa.String(), nullable=True),
        sa.Column("area_feddan", sa.String(), nullable=True, server_default="1.0"),
        sa.Column("turns", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("session_uuid"),
    )
    op.create_index("ix_conv_session_key", "conversation_sessions", ["session_key"], unique=False)
    op.create_index("ix_conv_project_id", "conversation_sessions", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_conv_project_id", table_name="conversation_sessions")
    op.drop_index("ix_conv_session_key", table_name="conversation_sessions")
    op.drop_table("conversation_sessions")