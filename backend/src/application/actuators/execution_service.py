"""Builds the decorated actuator port and reads the execution log."""

from typing import Any
from uuid import UUID

from src.application.actuators.dto import ExecutionDto
from src.application.devices.state_service import ActuatorNotFoundError
from src.domain.actuators.ports import ActuatorPort
from src.infrastructure.adapters.actuators.logging_decorator import LoggingActuatorDecorator
from src.infrastructure.adapters.actuators.max_runtime_decorator import MaxRunTimeActuatorDecorator
from src.infrastructure.adapters.actuators.selector import get_actuator_port
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.execution_log_repository import (
    ExecutionLogRepository,
    StoredExecution,
)

ACTUATOR_ROLE = "actuator"


class ActuatorExecutionService:
    def __init__(
        self,
        devices: DeviceRepository,
        states: ActuatorStateRepository,
        log: ExecutionLogRepository,
    ) -> None:
        self._devices = devices
        self._states = states
        self._log = log

    def port_for(self, device_id: UUID) -> ActuatorPort:
        """Logging, then max run time, then the real adapter."""
        device = self._devices.get_device(device_id)
        if device is None or device.role != ACTUATOR_ROLE:
            raise ActuatorNotFoundError(f"No actuator with id {device_id}.")

        inner = get_actuator_port(device)  # AdapterError if nothing can drive it
        return LoggingActuatorDecorator(
            MaxRunTimeActuatorDecorator(inner, self._states),
            self._log,
        )

    def apply(self, device_id: UUID, command: str, payload: dict[str, Any]) -> ExecutionDto:
        """Run one command through the chain and return the row it wrote."""
        self.port_for(device_id).apply(device_id, command, payload)
        return self.latest(device_id)

    def latest(self, device_id: UUID) -> ExecutionDto:
        return _to_dto(self._log.recent(1, device_id)[0])

    def recent(self, limit: int, device_id: UUID | None = None) -> list[ExecutionDto]:
        return [_to_dto(row) for row in self._log.recent(limit, device_id)]


def _to_dto(row: StoredExecution) -> ExecutionDto:
    return ExecutionDto(
        id=row.id,
        device_id=row.device_id,
        success=row.success,
        policy_applied=row.policy_applied,
        message=row.message,
        created_at=row.created_at,
    )