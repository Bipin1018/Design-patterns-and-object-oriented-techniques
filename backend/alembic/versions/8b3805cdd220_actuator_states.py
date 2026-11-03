"""actuator_states

Revision ID: 8b3805cdd220
Revises: 95a0aed75f6d
Create Date: 2026-11-03 10:36:40.896485

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b3805cdd220'
down_revision: Union[str, Sequence[str], None] = '95a0aed75f6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create actuator_states and give every existing actuator an idle row."""
    op.create_table(
        "actuator_states",
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("device_id"),
    )
    # Seed. Every actuator that already exists starts idle. Actuators created
    # later get their row when they are provisioned (ActuatorStateService.initialise).
    op.execute(
        """
        INSERT INTO actuator_states (device_id, state)
        SELECT id, 'idle' FROM devices WHERE role = 'actuator'
        ON CONFLICT (device_id) DO NOTHING
        """
    )


def downgrade() -> None:
    """Drop actuator_states. The devices themselves are untouched."""
    op.drop_table("actuator_states")