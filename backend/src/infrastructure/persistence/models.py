"""ORM models.

Phase 2 added devices. Phase 3 added device_family. Phase 4 adds locations and
zones, plus the two nullable columns on devices that record where a device sits.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func, text
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_devices_role", "role"),
        Index("ix_devices_family", "device_family"),
        Index("ix_devices_zone_id", "zone_id"),
    )