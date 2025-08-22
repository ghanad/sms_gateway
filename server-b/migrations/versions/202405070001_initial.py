"""initial

Revision ID: 202405070001
Revises: 
Create Date: 2024-05-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202405070001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tracking_id", sa.String, unique=True),
        sa.Column("client_key", sa.String),
        sa.Column("to", sa.String),
        sa.Column("text", sa.String),
        sa.Column("ttl_seconds", sa.Integer),
        sa.Column("provider_final", sa.String, nullable=True),
        sa.Column("status", sa.String),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_table(
        "message_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tracking_id", sa.String, sa.ForeignKey("messages.tracking_id")),
        sa.Column("event_type", sa.String),
        sa.Column("provider", sa.String, nullable=True),
        sa.Column("details", sa.JSON),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("message_events")
    op.drop_table("messages")
