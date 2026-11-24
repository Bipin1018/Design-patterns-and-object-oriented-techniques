"""ORM models.

Phase 2 added devices. Phase 3 added device_family. Phase 4 added locations and
zones, plus the two nullable columns on devices that record where a device sits.
Phase 5 adds sensor_readings and the two sampling columns the sampler reads.
Phase 6 adds automation_rules: which strategy a location decides with.
Phase 8 adds actuator_states: the lifecycle state of each actuator.
Phase 9 adds actuator_execution_log: every attempt to apply a command.
Phase 10 adds command_log: every command sent, with success, failed or rejected.
Phase 10 adds command_log: every command sent, with success, failed or rejected.
Phase 11 adds alerts: what the alert subscriber stored after a domain event.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.base import Base


class LocationRow(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    zones: Mapped[list["ZoneRow"]] = relationship(
        back_populates="location",
        cascade="all, delete-orphan",
        order_by="ZoneRow.created_at",
    )


class ZoneRow(Base):
    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # CASCADE: deleting a location takes its zones with it.
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Numeric keeps the stored value exact. The repository converts to float for
    # the domain, because SQLAlchemy hands Numeric back as Decimal.
    moisture_threshold_low: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    moisture_threshold_high: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    schedule: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    location: Mapped[LocationRow] = relationship(back_populates="zones")

    __table_args__ = (Index("ix_zones_location_id", "location_id"),)


class DeviceRow(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    device_type: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'sensor'"))
    device_family: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'simulation'")
    )
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    default_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # Phase 4. Both nullable: a device does not have to be placed anywhere.
    # The client only ever sends zone_id; location_id is copied from the zone.
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zones.id", ondelete="SET NULL"), nullable=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    # Phase 5. These two columns are the source of truth from this revision on.
    # The creators still copy the same interval into default_config, but nothing
    # reads it from there any more.
    sampling_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("300")
    )
    tracking_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_devices_role", "role"),
        Index("ix_devices_family", "device_family"),
        Index("ix_devices_zone_id", "zone_id"),
    )


class ReadingRow(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # CASCADE: deleting a device takes its readings with it. A reading with no
    # device is meaningless, whereas a device with no zone is perfectly normal.
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    # Numeric, not Float, for the same reason as the zone thresholds. It comes
    # back as Decimal, so the mapper calls float() before the JSON is built.
    value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # device_id first, then recorded_at: "the latest reading for this device"
    # narrows by device, then walks the timestamps. Ascending is enough, because
    # PostgreSQL reads a btree in either direction, so ORDER BY recorded_at DESC
    # LIMIT 1 uses this index as it stands.
    __table_args__ = (
        Index("ix_sensor_readings_device_recorded_at", "device_id", "recorded_at"),
    )


class AutomationRuleRow(Base):
    """Which strategy a location decides with.

    One row per location, enforced by the UNIQUE on location_id. That makes
    "one active strategy per location" something PostgreSQL refuses to break,
    rather than something the service has to remember.

    A location with no row has never had a strategy chosen. The service reads
    that as the default rather than as an error.
    """

    __tablename__ = "automation_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # CASCADE: deleting a location takes its rule with it, the same way it
    # takes its zones. A rule with no location decides nothing.
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # The key, not the class. The database stores a word; the domain owns what
    # that word means. Renaming a class never needs a migration.
    strategy_key: Mapped[str] = mapped_column(String(32), nullable=False)
    # Tuning numbers for a strategy that wants them. Stored and returned from
    # this phase on; nothing reads it yet. The column exists so that adding a
    # tuned strategy later is a code change, not a migration.
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ActuatorStateRow(Base):
    """Phase 8. The current lifecycle state of one actuator.

    One row per actuator, keyed by the device itself, so there is no second id
    to keep in step. CASCADE, because a state with no device means nothing.
    The row is updated in place on every legal transition. An illegal one is
    refused in the domain and never reaches this table.
    """

    __tablename__ = "actuator_states"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # off | idle | running | error | maintenance. The list of legal values and
    # the moves between them live in domain/actuators/state.py, not here.
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ActuatorExecutionLogRow(Base):
    """Phase 9. One row per attempt to apply a command to an actuator.

    Written by the logging decorator for successes and failures alike, so the
    dashboard shows what was tried, not only what worked. Rows are inserted and
    never updated.
    """

    __tablename__ = "actuator_execution_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # CASCADE, like sensor_readings: a log row for a deleted device means
    # nothing, and the test fixtures delete their devices afterwards.
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Names of the policies that took part, e.g. ["maxRunTime", "logging"].
    policy_applied: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Null on success. On failure, why: e.g. "Max run time exceeded".
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # created_at: the dashboard reads "the newest N rows".
    # device_id: PostgreSQL does not index a foreign key by itself.
    __table_args__ = (
        Index("ix_actuator_execution_log_created_at", "created_at"),
        Index("ix_actuator_execution_log_device_id", "device_id"),
    )


class CommandLogRow(Base):
    """Phase 10. One row per command sent to an actuator.

    Written by CommandService for success, failed and rejected alike, so the
    history also shows commands the state guard refused. An unknown command
    type or a missing device writes no row. Rows are inserted and never updated.
    """

    __tablename__ = "command_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # e.g. "start_pump", "stop_pump", "set_light_level".
    command_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # CASCADE, like the execution log: a row for a deleted device means nothing.
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    # What was sent with the command, e.g. {"level": 1}. Empty object if nothing.
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # success | failed | rejected. The CHECK below makes PostgreSQL refuse anything else.
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Null on success. Why it was rejected, or why it failed
    # (e.g. "Max run time exceeded").
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # created_at: the history reads "the newest N rows".
    # device_id: PostgreSQL does not index a foreign key by itself.
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failed', 'rejected')", name="ck_command_log_status"
        ),
        Index("ix_command_log_created_at", "created_at"),
        Index("ix_command_log_device_id", "device_id"),
    )
class AlertRow(Base):
    """Phase 11. One alert, written only by AlertPersistenceSubscriber.

    The three foreign keys are nullable and SET NULL, unlike the log tables
    above. An alert is history: deleting the pump or the zone it was about must
    not delete the record that something went wrong there. A device that was
    never placed in a zone stores null location_id and zone_id.
    """

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zones.id", ondelete="SET NULL"), nullable=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    # info | warning | critical
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # The event that caused it: threshold.crossed, command.failed, state.changed.
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # active | resolved. Phase 13 adds PATCH to resolve one.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'active'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Stored, not in the API response yet.
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # created_at: the feed reads "the newest N rows".
    # The three FKs: the filters use two of them, and PostgreSQL does not index
    # a foreign key by itself, so SET NULL on a delete would scan the table.
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')", name="ck_alerts_severity"
        ),
        CheckConstraint("status IN ('active', 'resolved')", name="ck_alerts_status"),
        Index("ix_alerts_created_at", "created_at"),
        Index("ix_alerts_location_id", "location_id"),
        Index("ix_alerts_zone_id", "zone_id"),
        Index("ix_alerts_device_id", "device_id"),
    )