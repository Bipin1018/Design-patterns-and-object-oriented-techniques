"""Use case for the sampling settings.

Small on purpose. The rule it enforces lives in the domain, so this class only
loads, validates and saves. Putting the 5 second floor here instead would mean
a second caller could quietly skip it.
"""

from uuid import UUID

from src.application.devices.dto import DeviceDto
from src.application.devices.mappers import device_to_dto
from src.application.readings.dto import UpdateSamplingRequestDto
from src.domain.devices.sampling import validate_sampling_interval
from src.infrastructure.persistence.device_repository import DeviceRepository


class DeviceNotFoundError(LookupError):
    """No device with that id. The router turns this into a 404."""


class SamplingService:
    def __init__(self, repository: DeviceRepository) -> None:
        self._repository = repository

    def update_sampling(self, device_id: UUID, request: UpdateSamplingRequestDto) -> DeviceDto:
        """Write both sampling columns.

        Validated before the write, so a rejected interval leaves the row
        exactly as it was. Same order as update_zone in Phase 4.
        """
        validate_sampling_interval(request.sampling_interval_seconds)  # ValueError -> 400

        device = self._repository.update_sampling(
            device_id,
            sampling_interval_seconds=request.sampling_interval_seconds,
            tracking_enabled=request.tracking_enabled,
        )
        if device is None:
            raise DeviceNotFoundError(f"No device with id {device_id}.")

        return device_to_dto(device)