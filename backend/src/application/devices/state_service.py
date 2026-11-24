"""Use case for actuator lifecycle: load, ask the domain, save.

The service never decides whether a move is legal. ActuatorContext does. The
service only owns the order: load the stored state, let the context guard the
move, and write only if the guard let it through.

Phase 11: this is the "ActuatorTransitionService" from the requirements.
After every successful save it publishes ActuatorStateChanged. It doesn't
know about alerts; the subscriber decides what an error means.
"""

from datetime import datetime
from uuid import UUID

from src.application.devices.dto import ActuatorStateDto, DeviceDto
from src.domain.actuators.context import ActuatorContext
from src.domain.actuators.state import INITIAL_STATE
from src.domain.events.bus import EventBus
from src.domain.events.events import ActuatorStateChanged
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository

ACTUATOR_ROLE = "actuator"


class ActuatorNotFoundError(LookupError):
    """No actuator with that id. A sensor id counts as missing. The router answers 404."""


class ActuatorStateService:
    def __init__(self, repository: ActuatorStateRepository, bus: EventBus) -> None:
        self._repository = repository
        self._bus = bus

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
        previous = stored.state if stored else INITIAL_STATE
        context = ActuatorContext(device_type, previous)

        context.transition(target)  # raises before anything is written

        saved = self._repository.save(device_id, context.state)

        # Publish after saving. An illegal move already raised above.
        location_id, zone_id = self._repository.placement(device_id)
        self._bus.publish(
            ActuatorStateChanged(
                device_id=device_id,
                location_id=location_id,
                zone_id=zone_id,
                previous_state=previous,
                state=saved.state,
            )
        )
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