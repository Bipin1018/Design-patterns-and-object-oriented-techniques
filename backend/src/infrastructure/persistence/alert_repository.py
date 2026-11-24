"""Reads and writes the alerts table. Nothing else touches it."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.persistence.models import AlertRow


@dataclass(frozen=True)
class StoredAlert:
    id: UUID
    location_id: UUID | None
    zone_id: UUID | None
    device_id: UUID | None
    severity: str
    message: str
    event_type: str
    status: str
    created_at: datetime
    acknowledged_at: datetime | None


class AlertRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        device_id: UUID | None,
        location_id: UUID | None,
        zone_id: UUID | None,
        severity: str,
        message: str,
        event_type: str,
    ) -> StoredAlert:
        """Save one active alert and return it."""
        row = AlertRow(
            device_id=device_id,
            location_id=location_id,
            zone_id=zone_id,
            severity=severity,
            message=message,
            event_type=event_type,
            status="active",
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)  # get the id and created_at from the database
        return self._to_stored(row)

    def list(
        self,
        *,
        status: str | None,
        location_id: UUID | None = None,
        zone_id: UUID | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[StoredAlert]:
        """Newest first. status=None means any status."""
        query = select(AlertRow)
        if status is not None:
            query = query.where(AlertRow.status == status)
        if location_id is not None:
            query = query.where(AlertRow.location_id == location_id)
        if zone_id is not None:
            query = query.where(AlertRow.zone_id == zone_id)
        if since is not None:
            query = query.where(AlertRow.created_at >= since)
        query = query.order_by(AlertRow.created_at.desc(), AlertRow.id.desc()).limit(limit)
        return [self._to_stored(row) for row in self._session.execute(query).scalars()]

    @staticmethod
    def _to_stored(row: AlertRow) -> StoredAlert:
        return StoredAlert(
            id=row.id,
            location_id=row.location_id,
            zone_id=row.zone_id,
            device_id=row.device_id,
            severity=row.severity,
            message=row.message,
            event_type=row.event_type,
            status=row.status,
            created_at=row.created_at,
            acknowledged_at=row.acknowledged_at,
        )