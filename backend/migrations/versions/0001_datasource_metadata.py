"""Store schema snapshots and business descriptions.

Revision ID: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "datasource_metadata",
        sa.Column("datasource_id", sa.String(100), primary_key=True),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("descriptions", postgresql.JSONB(), nullable=False),
        sa.Column(
            "synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("datasource_metadata")
