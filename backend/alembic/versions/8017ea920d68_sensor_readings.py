"""sensor_readings

Phase 5. Adds the readings table and the two sampling columns on devices.

Three statements here are hand-written, because autogenerate compares schema
and cannot know about data:

1. sampling_interval_seconds is backfilled from default_config, so a light
   sensor keeps its 60 seconds instead of dropping to the 300 default.
2. The protocol vocabulary moves to the words the Phase 5 adapters select on.
   Phase 3 wrote 'sim' and 'gpio-stub'; from here they are 'simulation' and
   'mqtt'. Sensors created through POST /api/sensors carried no protocol at
   all, so they get 'simulation'.
3. downgrade puts the old words back. It is best effort: rows that never had a
   protocol end up with 'sim', because the revision does not record which ones
   those were.

Revision ID: 8017ea920d68
Revises: 9589754ae217
Create Date: 2026-09-30 10:26:10.805752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8017ea920d68'
down_revision: Union[str, Sequence[str], None] = '9589754ae217'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Only rows whose JSON already holds a whole number are touched; the rest keep
# the 300 server default. GREATEST guards the 5 second floor the API enforces.
BACKFILL_INTERVAL = """
UPDATE devices
SET sampling_interval_seconds =
    GREATEST(5, (default_config ->> 'sampling_interval_seconds')::int)
WHERE jsonb_exists(default_config, 'sampling_interval_seconds')
  AND default_config ->> 'sampling_interval_seconds' ~ '^[0-9]+$'
"""

# jsonb_set creates the key when it is missing, which is what covers the
# Phase 2 sensors that never had a protocol.
PROTOCOL_TO_SIMULATION = """
UPDATE devices
SET default_config = jsonb_set(default_config, '{protocol}', '"simulation"')
WHERE default_config ->> 'protocol' = 'sim'
   OR NOT jsonb_exists(default_config, 'protocol')
"""

PROTOCOL_TO_MQTT = """
UPDATE devices
SET default_config = jsonb_set(default_config, '{protocol}', '"mqtt"')
WHERE default_config ->> 'protocol' = 'gpio-stub'
"""

PROTOCOL_BACK_TO_SIM = """
UPDATE devices
SET default_config = jsonb_set(default_config, '{protocol}', '"sim"')
WHERE default_config ->> 'protocol' = 'simulation'
"""

PROTOCOL_BACK_TO_GPIO_STUB = """
UPDATE devices
SET default_config = jsonb_set(default_config, '{protocol}', '"gpio-stub"')
WHERE default_config ->> 'protocol' = 'mqtt'
"""


def upgrade() -> None:
    """Upgrade schema, then repair the data the new columns depend on."""
    op.create_table('sensor_readings',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('device_id', sa.UUID(), nullable=False),
    sa.Column('value', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('unit', sa.String(length=16), nullable=False),
    sa.Column('source', sa.String(length=32), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sensor_readings_device_recorded_at', 'sensor_readings', ['device_id', 'recorded_at'], unique=False)
    # NOT NULL with a DEFAULT: PostgreSQL fills every existing row itself, the
    # same way device_family arrived in Phase 3.
    op.add_column('devices', sa.Column('sampling_interval_seconds', sa.Integer(), server_default=sa.text('300'), nullable=False))
    op.add_column('devices', sa.Column('tracking_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False))

    op.execute(BACKFILL_INTERVAL)
    op.execute(PROTOCOL_TO_SIMULATION)
    op.execute(PROTOCOL_TO_MQTT)


def downgrade() -> None:
    """Undo the data moves first, then drop the schema."""
    op.execute(PROTOCOL_BACK_TO_SIM)
    op.execute(PROTOCOL_BACK_TO_GPIO_STUB)

    op.drop_column('devices', 'tracking_enabled')
    op.drop_column('devices', 'sampling_interval_seconds')
    op.drop_index('ix_sensor_readings_device_recorded_at', table_name='sensor_readings')
    op.drop_table('sensor_readings')