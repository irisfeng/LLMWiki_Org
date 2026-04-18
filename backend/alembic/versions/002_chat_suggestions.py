"""Add chat_suggestions cache table

Revision ID: 002_chat_suggestions
Revises: 001_wiki_chunks
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "002_chat_suggestions"
down_revision = "001_wiki_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("related_slug", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("chat_suggestions")
