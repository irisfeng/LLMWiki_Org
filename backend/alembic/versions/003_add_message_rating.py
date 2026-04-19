"""Add rating column to chat_messages

Revision ID: 003_message_rating
Revises: 002_chat_suggestions
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa


revision = "003_message_rating"
down_revision = "002_chat_suggestions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("rating", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "rating")
