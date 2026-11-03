"""Use case for actuator lifecycle: load, ask the domain, save.

The service never decides whether a move is legal. ActuatorContext does. The
service only owns the order: load the stored state, let the context guard the
move, and write only if the guard let it through.
"""

from datetime import datetime
from uuid import UUID

from src.application.devices.dto import ActuatorStateDto, DeviceDto
from src.domain.actuators.context import ActuatorContext
from src.domain.actuators.state import INITIAL_STATE
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository

ACTUATOR_ROLE = "actuator"


class ActuatorNotFoundError(LookupError):
    """No actuator with that id. A sensor id counts as missing. The router answers 404."""


class ActuatorStateService:
    def __init__(self, repository: ActuatorStateRepository) -> None:
        self._repository = repository

    # -- Read side: put state on device DTOs ----------------------------------

    def attach(self, devices: list[DeviceDto]) -> list[DeviceDto]:
        """Fill state and allowed_commands on every actuator, in one query.

        Sensors pass through with null and []. An actuator with no stored row
        (only possible if it was inserted outside provisioning) shows the
        initial state, and its row is written on its first transition.
        """
        stored = self._repository.get_many(
            device.id for device in devices if device.role == ACTUATOR_ROLE
        )
        return [
            self._with_state(device, stored.get(device.id, INITIAL_STATE))
            if device.role == ACTUATOR_ROLE
            else device
            for device in devices
        ]

    def attach_one(self, device: DeviceDto) -> DeviceDto:
        return self.attach([device])[0]

    def initialise(self, devices: list[DeviceDto]) -> list[DeviceDto]:
        """Store an idle row for newly provisioned actuators, then attach."""
        self._repository.ensure(
            [device.id for device in devices if device.role == ACTUATOR_ROLE],
            INITIAL_STATE,
        )
        return self.attach(devices)

    def get_state(self, device_id: UUID) -> ActuatorStateDto:
        device_type = self._require_actuator(device_id)
        stored = self._repository.get(device_id)
        if stored is None:
            return self._to_dto(device_id, ActuatorContext(device_type), None)
        context = ActuatorContext(device_type, stored.state)
        return self._to_dto(device_id, context, stored.updated_at)

    # -- Write side ------------------------------------------------------------

    def transition(self, device_id: UUID, target: str) -> ActuatorStateDto:
        """Move one actuator. Nothing is written unless the domain allows the edge."""
        device_type = self._require_actuator(device_id)
        # Locked, so two requests at once cannot both pass the guard from the
        # same starting state.
        stored = self._repository.get(device_id, for_update=True)
        context = ActuatorContext(device_type, stored.state if stored else INITIAL_STATE)

        context.transition(target)  # raises before anything is written

        saved = self._repository.save(device_id, context.state)
        return self._to_dto(device_id, context, saved.updated_at)

    # -- Helpers ---------------------------------------------------------------

    def _require_actuator(self, device_id: UUID) -> str:
        device_type = self._repository.actuator_type(device_id)
        if device_type is None:
            raise ActuatorNotFoundError(f"No actuator with id {device_id}.")
        return device_type

    @staticmethod
    def _with_state(device: DeviceDto, state: str) -> DeviceDto:
        context = ActuatorContext(device.device_type, state)
        return device.model_copy(
            update={"state": context.state, "allowed_commands": context.allowed_commands()}
        )

    @staticmethod
    def _to_dto(
        device_id: UUID, context: ActuatorContext, updated_at: datetime | None
    ) -> ActuatorStateDto:
        return ActuatorStateDto(
            device_id=device_id,
            state=context.state,
            allowed_commands=context.allowed_commands(),
            updated_at=updated_at,
        )