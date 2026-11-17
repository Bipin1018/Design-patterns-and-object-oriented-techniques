"""HTTP routes for commands and the command history.

The routes only call CommandService and turn its errors into status codes.
They never touch an actuator port themselves.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from src.application.actuators.execution_service import ActuatorExecutionService
from src.application.commands.dto import CommandLogDto, CommandRequestDto
from src.application.commands.service import CommandService
from src.application.devices.state_service import ActuatorNotFoundError, ActuatorStateService
from src.domain.commands.base import REJECTED
from src.infrastructure.db import get_db
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository
from src.infrastructure.persistence.command_log_repository import CommandLogRepository
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.execution_log_repository import ExecutionLogRepository

router = APIRouter(prefix="/api/commands", tags=["commands"])


def get_command_service(session: Session = Depends(get_db)) -> CommandService:
    states = ActuatorStateRepository(session)
    executions = ActuatorExecutionService(
        DeviceRepository(session), states, ExecutionLogRepository(session)
    )
    return CommandService(
        states,
        ActuatorStateService(states),
        executions,
        CommandLogRepository(session),
    )


@router.post(
    "",
    response_model=CommandLogDto,
    summary="Run a command on an actuator",
    description=(
        "Checks the command against the actuator's allowed_commands, sends it through "
        "the logging and max-run-time decorators, updates the state and writes one "
        "command_log row. 200 for success and failed, 409 for rejected (same row shape)."
    ),
    responses={
        400: {"description": "Unknown command_type or bad payload. No row is written."},
        404: {"description": "No actuator with that id (sensors count as missing)."},
        409: {
            "model": CommandLogDto,
            "description": "Not allowed in the current state. The rejected row is still written.",
        },
    },
)
def submit_command(
    body: CommandRequestDto,
    response: Response,
    service: CommandService = Depends(get_command_service),
) -> CommandLogDto:
    try:
        row = service.submit(body.command_type, body.device_id, body.payload)
    except ActuatorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:  # unknown command_type or bad payload
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if row.status == REJECTED:
        response.status_code = status.HTTP_409_CONFLICT
    return row


@router.get(
    "",
    response_model=list[CommandLogDto],
    summary="Command history",
    description="Newest first. Includes success, failed and rejected commands.",
)
def list_commands(
    limit: int = Query(default=50, ge=1, le=200, description="How many rows."),
    service: CommandService = Depends(get_command_service),
) -> list[CommandLogDto]:
    return service.recent(limit)