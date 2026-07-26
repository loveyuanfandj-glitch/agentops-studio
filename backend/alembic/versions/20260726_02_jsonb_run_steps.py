"""Use JSONB for structured run-step payloads on PostgreSQL."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260726_02"
down_revision = "20260726_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for column in ("arguments", "output"):
        op.alter_column(
            "run_steps",
            column,
            existing_type=sa.JSON(),
            type_=postgresql.JSONB(),
            postgresql_using=f"{column}::jsonb",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for column in ("arguments", "output"):
        op.alter_column(
            "run_steps",
            column,
            existing_type=postgresql.JSONB(),
            type_=sa.JSON(),
            postgresql_using=f"{column}::json",
        )
