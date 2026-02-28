"""Add trends, epa_data JSONB columns and webhook_subscriptions table.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-01 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add JSONB columns to tract_profiles
    op.add_column(
        "tract_profiles",
        sa.Column("trends", postgresql.JSONB(), nullable=True,
                  comment="Year-keyed historical ACS snapshots"),
    )
    op.add_column(
        "tract_profiles",
        sa.Column("epa_data", postgresql.JSONB(), nullable=True,
                  comment="EPA EJScreen environmental indicators"),
    )

    # Create webhook_subscriptions table
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("url", sa.Text(), nullable=False,
                  comment="Callback URL for webhook delivery"),
        sa.Column("api_key_hash", sa.String(64), nullable=False,
                  comment="SHA-256 hash of owning API key"),
        sa.Column("events", postgresql.JSONB(), nullable=False,
                  comment="List of subscribed event types"),
        sa.Column("filters", postgresql.JSONB(), nullable=True,
                  comment="Optional filters: state_fips, geoids, thresholds"),
        sa.Column("secret", sa.String(64), nullable=True,
                  comment="Shared secret for HMAC signature verification"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_webhook_subscriptions_api_key_hash",
                    "webhook_subscriptions", ["api_key_hash"])


def downgrade() -> None:
    op.drop_index("ix_webhook_subscriptions_api_key_hash",
                  table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")
    op.drop_column("tract_profiles", "epa_data")
    op.drop_column("tract_profiles", "trends")
