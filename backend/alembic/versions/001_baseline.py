"""baseline — no business tables

Phase 1 ships an intentionally empty migration. Applying it creates only the
alembic_version bookkeeping table, which proves the toolchain reaches
PostgreSQL and gives Phase 2 a parent revision to build the devices table on.

Revision ID: 001_baseline
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "001_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Intentionally empty — no business tables in Phase 1."""
    pass


def downgrade() -> None:
    """Downgrade schema. Nothing to undo."""
    pass
