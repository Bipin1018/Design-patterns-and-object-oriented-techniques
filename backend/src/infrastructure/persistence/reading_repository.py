"""Persistence for sensor readings.

Append-only. There is no update method and no delete method, because a reading
is a record of what a sensor said at a moment. Correcting one would be lying
about the past.

The only place that knows both the Reading value object and SQLAlchemy.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.domain.sensors.reading import Reading
from src.infrastructure.persistence.models import ReadingRow


class ReadingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert(self, reading: Reading) -> Reading:
        """Store one reading and return it with the stored timestamp."""
        row = ReadingRow(
            device_id=reading.device_id,
            value=reading.value,
            unit=reading.unit,
            source=reading.source,
            recorded_at=reading.recorded_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_reading(row)

    def list_for_device(self, device_id: UUID, limit: int = 20) -> list[Reading]:
        """The most recent readings for one device, newest first.

        ORDER BY recorded_at DESC with a LIMIT is the query the composite index
        was built for: it narrows by device_id, then walks the timestamps
        backwards and stops.
        """
        statement = (
            select(ReadingRow)
            .where(ReadingRow.device_id == device_id)
            .order_by(ReadingRow.recorded_at.desc())
            .limit(limit)
        )
        rows = self._session.execute(statement).scalars().all()
        return [self._to_reading(row) for row in rows]

    def latest_recorded_at(self, device_ids: list[UUID]) -> dict[UUID, datetime]:
        """When each of these devices was last recorded.

        One grouped query rather than one query per device. The sampler runs on
        a timer with every simulation sensor in hand, so asking the database
        once per tick instead of once per device is the difference between a
        handful of queries a minute and hundreds.

        Devices with no reading yet are simply absent from the result, which
        the sampler reads as "due".
        """
        if not device_ids:
            return {}

        statement = (
            select(ReadingRow.device_id, func.max(ReadingRow.recorded_at))
            .where(ReadingRow.device_id.in_(device_ids))
            .group_by(ReadingRow.device_id)
        )
        return {row[0]: row[1] for row in self._session.execute(statement)}

    def count_for_device(self, device_id: UUID) -> int:
        """How many readings this device has. Used by the tests."""
        statement = (
            select(func.count())
            .select_from(ReadingRow)
            .where(ReadingRow.device_id == device_id)
        )
        return int(self._session.execute(statement).scalar_one())

    @staticmethod
    def _to_reading(row: ReadingRow) -> Reading:
        return Reading(
            device_id=row.device_id,
            # Numeric comes back as Decimal. float() here is what keeps the
            # JSON a number instead of a string, same as the zone thresholds.
            value=float(row.value),
            unit=row.unit,
            source=row.source,
            recorded_at=row.recorded_at,
        )