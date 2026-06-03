"""add knowledge store tables

Revision ID: 2c9f1a4f9c11
Revises: dc0ed7683d63
Create Date: 2026-06-02 16:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2c9f1a4f9c11"
down_revision: Union[str, None] = "dc0ed7683d63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("source_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_uuid", sa.UUID(), nullable=False),
        sa.Column("source_project_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("source_country", sa.String(), nullable=True),
        sa.Column("source_language", sa.String(), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_project_id"], ["projects.project_id"]),
        sa.PrimaryKeyConstraint("source_id"),
        sa.UniqueConstraint("source_uuid"),
    )
    op.create_index("ix_knowledge_source_project_id", "knowledge_sources", ["source_project_id"], unique=False)
    op.create_index("ix_knowledge_source_name", "knowledge_sources", ["source_name"], unique=False)

    op.create_table(
        "knowledge_records",
        sa.Column("record_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("record_uuid", sa.UUID(), nullable=False),
        sa.Column("record_project_id", sa.Integer(), nullable=False),
        sa.Column("record_source_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("disease", sa.String(), nullable=True),
        sa.Column("pest", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("normalized_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("record_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["record_project_id"], ["projects.project_id"]),
        sa.ForeignKeyConstraint(["record_source_id"], ["knowledge_sources.source_id"]),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint("record_uuid"),
    )
    op.create_index("ix_knowledge_record_project_id", "knowledge_records", ["record_project_id"], unique=False)
    op.create_index("ix_knowledge_record_name", "knowledge_records", ["name"], unique=False)
    op.create_index("ix_knowledge_record_topic", "knowledge_records", ["topic"], unique=False)
    op.create_index("ix_knowledge_record_disease", "knowledge_records", ["disease"], unique=False)
    op.create_index("ix_knowledge_record_pest", "knowledge_records", ["pest"], unique=False)

    op.create_table(
        "knowledge_feedback",
        sa.Column("feedback_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feedback_uuid", sa.UUID(), nullable=False),
        sa.Column("feedback_project_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("feedback", sa.String(), nullable=False),
        sa.Column("feedback_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["feedback_project_id"], ["projects.project_id"]),
        sa.PrimaryKeyConstraint("feedback_id"),
        sa.UniqueConstraint("feedback_uuid"),
    )
    op.create_index("ix_knowledge_feedback_project_id", "knowledge_feedback", ["feedback_project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_knowledge_feedback_project_id", table_name="knowledge_feedback")
    op.drop_table("knowledge_feedback")
    op.drop_index("ix_knowledge_record_pest", table_name="knowledge_records")
    op.drop_index("ix_knowledge_record_disease", table_name="knowledge_records")
    op.drop_index("ix_knowledge_record_topic", table_name="knowledge_records")
    op.drop_index("ix_knowledge_record_name", table_name="knowledge_records")
    op.drop_index("ix_knowledge_record_project_id", table_name="knowledge_records")
    op.drop_table("knowledge_records")
    op.drop_index("ix_knowledge_source_name", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_source_project_id", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
