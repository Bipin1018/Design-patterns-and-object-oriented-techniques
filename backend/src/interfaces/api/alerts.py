"""GET /api/alerts. Read only: alerts are created by the subscriber, not here."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.alerts.dto import ACTIVE, AlertDto
from src.application.alerts.service import AlertService, InvalidAlertStatusError
from src.infrastructure.db import get_db
from src.infrastructure.persistence.alert_repository import AlertRepository

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def get_alert_service(session: Session = Depends(get_db)) -> AlertService:
    return AlertService(AlertRepository(session))


@router.get(
    "",
    response_model=list[AlertDto],
    summary="List alerts",
    description=(
        "Newest first. An alert is saved when moisture drops below its zone's low "
        "threshold (`threshold.crossed`, warning), a command fails (`command.failed`, "
        "warning) or an actuator enters error (`state.changed`, critical). Alerts from a "
        "device with no zone have null `location_id` and `zone_id`."
    ),
    responses={400: {"description": "status is not active, resolved or all."}},
)
def list_alerts(
    status_filter: str = Query(
        default=ACTIVE,
        alias="status",
        description="active (default), resolved or all.",
    ),
    location_id: UUID | None = Query(default=None, description="Only this location."),
    zone_id: UUID | None = Query(default=None, description="Only this zone."),
    since: datetime | None = Query(
        default=None,
        description="Only alerts created at or after this time, e.g. 2026-11-24T08:00:00Z.",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="How many rows (1-200)."),
    service: AlertService = Depends(get_alert_service),
) -> list[AlertDto]:
    try:
        return service.list_alerts(
            status=status_filter,
            location_id=location_id,
            zone_id=zone_id,
            since=since,
            limit=limit,
        )
    except InvalidAlertStatusError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc