"""HTTP route for the actuator execution log.

Commands are sent through POST /api/commands (Phase 10), never from here.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.application.actuators.dto import ExecutionDto
from src.application.actuators.execution_service import ActuatorExecutionService
from src.infrastructure.db import get_db
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.execution_log_repository import ExecutionLogRepository

router = APIRouter(prefix="/api/actuators", tags=["actuators"])


def get_execution_service(session: Session = Depends(get_db)) -> ActuatorExecutionService:
    return ActuatorExecutionService(
        DeviceRepository(session),
        ActuatorStateRepository(session),
        ExecutionLogRepository(session),
    )


@router.get(
    "/executions",
    response_model=list[ExecutionDto],
    summary="Recent actuator executions",
    description=(
        "Newest first. One row per attempt, successful or blocked. "
        'A blocked row has success false and policy_applied ["maxRunTime", "logging"].'
    ),
)
def list_executions(
    limit: int = Query(default=20, ge=1, le=100, description="How many rows."),
    device_id: UUID | None = Query(default=None, description="Only this actuator."),
    service: ActuatorExecutionService = Depends(get_execution_service),
) -> list[ExecutionDto]:
    return service.recent(limit, device_id)