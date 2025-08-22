from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String, nullable=False, unique=True),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("role", sa.String, nullable=False),
    )
    op.create_table(
        "user_providers",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("provider", sa.String, primary_key=True),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("to", sa.String, nullable=False),
        sa.Column("text", sa.String),
        sa.Column("provider", sa.String),
        sa.Column("status", sa.String),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow),
    )
    op.create_index("ix_messages_to", "messages", ["to"])
    op.create_index("ix_messages_provider", "messages", ["provider"])
    op.create_index("ix_messages_status", "messages", ["status"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])


def downgrade():
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_status", table_name="messages")
    op.drop_index("ix_messages_provider", table_name="messages")
    op.drop_index("ix_messages_to", table_name="messages")
    op.drop_table("messages")
    op.drop_table("user_providers")
    op.drop_table("users")
