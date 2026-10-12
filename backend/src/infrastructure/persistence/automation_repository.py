"""Persistence for automation: the saved rule, and the facts a decision needs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.domain.automation.rule import AutomationRule
from src.infrastructure.persistence.models import (
    AutomationRuleRow,
    DeviceRow,
    LocationRow,
    ReadingRow,
    ZoneRow,
)

#: The device_type values a zone's moisture and light readings come from.
MOISTURE_SENSOR_TYPE = "moisture_sensor"
LIGHT_SENSOR_TYPE = "light_sensor"


@dataclass(frozen=True)
class ZoneThresholds:
    """One zone's band, already cast out of Decimal."""

    zone_id: UUID
    name: str
    moisture_low: float
    moisture_high: float


@dataclass(frozen=True)
class LatestReading:
    """The newest reading in a zone, and which device produced it."""

    device_id: UUID
    value: float
    unit: str
    recorded_at: datetime


class AutomationRuleRepository:
    """Reads and writes the one row per location in automation_rules."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, location_id: UUID) -> AutomationRule | None:
        """The saved rule, or None if this location has never chosen one.

        None is a real answer, not an error. The service reads it as "use the
        default" rather than refusing to evaluate.
        """
        row = self._session.execute(
            select(AutomationRuleRow).where(AutomationRuleRow.location_id == location_id)
        ).scalar_one_or_none()
        return None if row is None else self._to_rule(row)

    def upsert(
        self,
        location_id: UUID,
        strategy_key: str,
        parameters: dict[str, Any] | None = None,
    ) -> AutomationRule:
        """Save the choice, replacing any previous one for this location.

        One statement, leaning on the UNIQUE constraint rather than on a read
        followed by a write. Two requests arriving together cannot both insert.

        updated_at is set explicitly because the model's onupdate hook only
        fires for ORM updates, and this is a Core insert with a conflict clause.
        """
        statement = (
            pg_insert(AutomationRuleRow)
            .values(
                location_id=location_id,
                strategy_key=strategy_key,
                parameters=parameters or {},
            )
            .on_conflict_do_update(
                index_elements=[AutomationRuleRow.location_id],
                set_={
                    "strategy_key": strategy_key,
                    "parameters": parameters or {},
                    "updated_at": func.now(),
                },
            )
            .returning(AutomationRuleRow)
        )
        row = self._session.execute(statement).scalar_one()
        rule = self._to_rule(row)
        self._session.commit()
        return rule

    @staticmethod
    def _to_rule(row: AutomationRuleRow) -> AutomationRule:
        return AutomationRule(
            location_id=row.location_id,
            strategy_key=row.strategy_key,
            parameters=dict(row.parameters or {}),
            updated_at=row.updated_at,
        )


class AutomationContextRepository:
    """Assembles the facts a decision needs, one location at a time."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def location_name(self, location_id: UUID) -> str | None:
        """The name, or None if there is no such location.

        Returning the name rather than the row keeps LocationRow inside this
        module, and the service needs the name anyway for its reasons.
        """
        return self._session.execute(
            select(LocationRow.name).where(LocationRow.id == location_id)
        ).scalar_one_or_none()

    def zone_thresholds(self, location_id: UUID) -> list[ZoneThresholds]:
        """Every zone in the location, with its band as floats.

        float() is not optional. Numeric comes back as Decimal, and comparing a
        Decimal against a float reading loses precision at best. Same trap as
        Phase 4's mapper.
        """
        rows = (
            self._session.execute(
                select(ZoneRow)
                .where(ZoneRow.location_id == location_id)
                .order_by(ZoneRow.created_at)
            )
            .scalars()
            .all()
        )
        return [
            ZoneThresholds(
                zone_id=row.id,
                name=row.name,
                moisture_low=float(row.moisture_threshold_low),
                moisture_high=float(row.moisture_threshold_high),
            )
            for row in rows
        ]

    def latest_by_zone(
        self,
        zone_ids: list[UUID],
        device_type: str,
    ) -> dict[UUID, LatestReading]:
        """The newest reading of one device type in each of these zones.

        DISTINCT ON (devices.zone_id) with ORDER BY zone_id, recorded_at DESC:
        PostgreSQL walks each zone's readings newest first and keeps the first
        row. One query for the whole location rather than one per zone.

        The join is the requirement made literal. A reading counts for a zone
        only if the device that produced it carries that zone_id, so a device
        with zone_id NULL is never borrowed by a zone with no sensor of its own.
        """
        if not zone_ids:
            return {}

        statement = (
            select(
                DeviceRow.zone_id,
                ReadingRow.device_id,
                ReadingRow.value,
                ReadingRow.unit,
                ReadingRow.recorded_at,
            )
            .select_from(ReadingRow)
            .join(DeviceRow, DeviceRow.id == ReadingRow.device_id)
            .where(DeviceRow.zone_id.in_(zone_ids))
            .where(DeviceRow.device_type == device_type)
            .distinct(DeviceRow.zone_id)
            .order_by(DeviceRow.zone_id, ReadingRow.recorded_at.desc())
        )

        return {
            row.zone_id: LatestReading(
                device_id=row.device_id,
                value=float(row.value),
                unit=row.unit,
                recorded_at=row.recorded_at,
            )
            for row in self._session.execute(statement)
        }