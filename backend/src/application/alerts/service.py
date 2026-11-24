"""Reads alerts for GET /api/alerts. Writing happens only in the subscriber."""

from datetime import datetime
from uuid import UUID

from src.application.alerts.dto import ALL, STATUS_FILTERS, AlertDto
from src.infrastructure.persistence.alert_repository import AlertRepository, StoredAlert


class InvalidAlertStatusError(ValueError):
    """status wasn't active, resolved or all. The router returns 400."""


class AlertService:
    def __init__(self, repository: AlertRepository) -> None:
        self._repository = repository

    def list_alerts(
        self,
        *,
        status: str,
        location_id: UUID | None = None,
        zone_id: UUID | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[AlertDto]:
        """Newest first."""
        if status not in STATUS_FILTERS:
            raise InvalidAlertStatusError(
                f"Unknown status {status!r}. Use one of: {', '.join(STATUS_FILTERS)}."
            )
        rows = self._repository.list(
            status=None if status == ALL else status,  # "all" means no status filter
            location_id=location_id,
            zone_id=zone_id,
            since=since,
            limit=limit,
        )
        return [_to_dto(row) for row in rows]


def _to_dto(row: StoredAlert) -> AlertDto:
    return AlertDto(
        id=row.id,
        location_id=row.location_id,
        zone_id=row.zone_id,
        device_id=row.device_id,
        severity=row.severity,
        message=row.message,
        event_type=row.event_type,
        status=row.status,
        created_at=row.created_at,
    )