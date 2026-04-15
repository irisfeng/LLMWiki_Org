"""Add wiki_chunks table for fine-grained retrieval

Revision ID: 001_wiki_chunks
Revises:
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


revision = "001_wiki_chunks"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "wiki_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("heading_path", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_wiki_chunks_page_id", "wiki_chunks", ["page_id"])
    op.create_index("ix_wiki_chunks_page_position", "wiki_chunks", ["page_id", "position"])
    # IVFFlat index for vector similarity (created when data exists; safe to run now)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_wiki_chunks_embedding "
        "ON wiki_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_index("ix_wiki_chunks_embedding", table_name="wiki_chunks")
    op.drop_index("ix_wiki_chunks_page_position", table_name="wiki_chunks")
    op.drop_index("ix_wiki_chunks_page_id", table_name="wiki_chunks")
    op.drop_table("wiki_chunks")
