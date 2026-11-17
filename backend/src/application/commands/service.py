"""Runs one command: check it, send it, update the state, log it.

Every attempt that passes the device and name checks gets one command_log row:
success, failed or rejected.
"""

from typing import Any
from uuid import UUID

from src.application.actuators.execution_service import ActuatorExecutionService
from src.application.commands.dto import CommandLogDto
from src.application.devices.state_service import ActuatorNotFoundError, ActuatorStateService
from src.domain.actuators.context import ActuatorContext
from src.domain.actuators.policies import ActuatorPolicyError
from src.domain.actuators.state import INITIAL_STATE
from src.domain.commands.base import FAILED, REJECTED, SUCCESS, Command
from src.domain.commands.invoker import CommandInvoker, command_for
from src.domain.sensors.errors import AdapterError
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository
from src.infrastructure.persistence.command_log_repository import (
    CommandLogRepository,
    StoredCommand,
)


class CommandService:
    def __init__(
        self,
        states: ActuatorStateRepository,
        state_service: ActuatorStateService,
        executions: ActuatorExecutionService,
        log: CommandLogRepository,
        invoker: CommandInvoker | None = None,
    ) -> None:
        self._states = states
        self._state_service = state_service
        self._executions = executions
        self._log = log
        self._invoker = invoker or CommandInvoker()

    def submit(self, command_type: str, device_id: UUID, payload: dict[str, Any]) -> CommandLogDto:
        """Run one command and return the command_log row it wrote."""
        # 1. An actuator? A sensor id counts as missing, as in Phase 8.
        device_type = self._states.actuator_type(device_id)
        if device_type is None:
            raise ActuatorNotFoundError(f"No actuator with id {device_id}.")

        # 2. Registry lookup. Unknown name or bad payload raises a ValueError: 400, no row.
        command = command_for(command_type, device_id, payload)

        # 3. State guard. Rejected: write the row and stop. No apply, no state write.
        stored = self._states.get(device_id)
        context = ActuatorContext(device_type, stored.state if stored else INITIAL_STATE)
        allowed = context.allowed_commands()
        if command.command_type not in allowed:
            return self._write(
                command,
                REJECTED,
                f"{command.command_type!r} is not allowed while {context.state}. "
                f"Allowed now: {', '.join(allowed) or 'none'}.",
            )

        # 4. Execute through the decorated port (logging -> max run time -> adapter).
        try:
            self._invoker.run(command, self._executions.port_for(device_id))
        except ActuatorPolicyError as exc:  # e.g. "Max run time exceeded"
            return self._write(command, FAILED, exc.message)
        except AdapterError as exc:  # no adapter can drive this device
            return self._write(command, FAILED, str(exc))

        # 5. Move the state only when the target differs. set_light_level on a
        #    running light stays running, so nothing is transitioned.
        if command.target_state != context.state:
            self._state_service.transition(device_id, command.target_state)

        return self._write(command, SUCCESS, None)

    def recent(self, limit: int) -> list[CommandLogDto]:
        """Newest first."""
        return [_to_dto(row) for row in self._log.recent(limit)]

    def _write(self, command: Command, status: str, error_message: str | None) -> CommandLogDto:
        stored = self._log.add(
            command.device_id,
            command.command_type,
            command.payload,
            status=status,
            error_message=error_message,
        )
        return _to_dto(stored)


def _to_dto(row: StoredCommand) -> CommandLogDto:
    return CommandLogDto(
        id=row.id,
        command_type=row.command_type,
        device_id=row.device_id,
        payload=row.payload,
        status=row.status,
        error_message=row.error_message,
        created_at=row.created_at,
    )