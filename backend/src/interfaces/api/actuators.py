"""HTTP routes for actuator commands and the execution log."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.actuators.dto import ApplyRequestDto, ExecutionDto
from src.application.actuators.execution_service import ActuatorExecutionService
from src.application.devices.state_service import ActuatorNotFoundError
from src.domain.actuators.policies import ActuatorPolicyError
from src.domain.sensors.errors import AdapterError
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


@router.post(
    "/{device_id}/apply",
    response_model=ExecutionDto,
    summary="Apply a command through the decorated port (demo)",
    description=(
        "Goes through logging, then max run time, then the adapter. The command is "
        "not checked in this phase. Blocked once the actuator has been running for "
        "30 minutes. Every call writes a log row. Replaced by Command in Phase 10."
    ),
    responses={
        400: {"description": "No adapter can drive this device."},
        404: {"description": "No actuator with that id (sensors count as missing)."},
        409: {"description": "A policy blocked the command. The row is still written."},
    },
)
def apply_command(
    device_id: UUID,
    payload: ApplyRequestDto,
    service: ActuatorExecutionService = Depends(get_execution_service),
) -> ExecutionDto:
    try:
        return service.apply(device_id, payload.command, payload.payload)
    except ActuatorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ActuatorPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except AdapterError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc