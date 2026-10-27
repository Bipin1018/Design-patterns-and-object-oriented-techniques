"""Read-side queries for the location overview."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.infrastructure.persistence.models import DeviceRow, LocationRow, ReadingRow


@dataclass(frozen=True)
class OverviewZone:
    id: UUID
    name: str
    moisture_threshold_low: float
    moisture_threshold_high: float


@dataclass(frozen=True)
class OverviewLocation:
    id: UUID
    name: str
    zones: tuple[OverviewZone, ...]


@dataclass(frozen=True)
class AssignedDevice:
    id: UUID
    zone_id: UUID
    device_type: str
    role: str
    display_name: str | None
    tracking_enabled: bool
    sampling_interval_seconds: int


@dataclass(frozen=True)
class NewestReading:
    device_id: UUID
    value: float
    unit: str
    recorded_at: datetime


class OverviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def location_with_zones(self, location_id: UUID) -> OverviewLocation | None:
        row = self._session.execute(
            select(LocationRow)
            .options(selectinload(LocationRow.zones))
            .where(LocationRow.id == location_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        return OverviewLocation(
            id=row.id,
            name=row.name,
            zones=tuple(
                OverviewZone(
                    id=zone.id,
                    name=zone.name,
                    moisture_threshold_low=float(zone.moisture_threshold_low),
                    moisture_threshold_high=float(zone.moisture_threshold_high),
                )
                for zone in row.zones
            ),
        )

    def assigned_devices(self, location_id: UUID) -> list[AssignedDevice]:
        rows = (
            self._session.execute(
                select(DeviceRow)
                .where(DeviceRow.location_id == location_id, DeviceRow.zone_id.is_not(None))
                .order_by(DeviceRow.created_at)
            )
            .scalars()
            .all()
        )
        return [
            AssignedDevice(
                id=row.id,
                zone_id=row.zone_id,
                device_type=row.device_type,
                role=row.role,
                display_name=row.display_name,
                tracking_enabled=row.tracking_enabled,
                sampling_interval_seconds=row.sampling_interval_seconds,
            )
            for row in rows
        ]

    def newest_readings(self, device_ids: list[UUID]) -> dict[UUID, NewestReading]:
        if not device_ids:
            return {}
        rows = (
            self._session.execute(
                select(ReadingRow)
                .where(ReadingRow.device_id.in_(device_ids))
                .order_by(ReadingRow.device_id, ReadingRow.recorded_at.desc())
                .distinct(ReadingRow.device_id)
            )
            .scalars()
            .all()
        )
        return {
            row.device_id: NewestReading(
                device_id=row.device_id,
                value=float(row.value),
                unit=row.unit,
                recorded_at=row.recorded_at,
            )
            for row in rows
        }