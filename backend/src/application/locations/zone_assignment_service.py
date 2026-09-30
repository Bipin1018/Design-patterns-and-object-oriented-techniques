"""Placing devices in zones.

Separate from the builder on purpose. A zone has no id until the config is
saved, and the devices already exist from Phases 2 and 3, so placement is an
update afterwards, never a rebuild of the location.
"""

from uuid import UUID

from src.application.locations.config_service import LocationNotFoundError
from src.domain.devices.entity import Device
from src.infrastructure.persistence.location_repository import LocationRepository
from src.infrastructure.persistence.models import DeviceRow


class ZoneAssignmentService:
    def __init__(self, repository: LocationRepository) -> None:
        self._repository = repository

    def assign(self, device_id: UUID, zone_id: UUID | None) -> Device:
        """Place a device in a zone, or clear its placement when zone_id is None."""
        device_row = self._repository.get_device(device_id)
        if device_row is None:
            raise LocationNotFoundError(f"No device with id {device_id}.")

        if zone_id is None:
            return _to_device(self._repository.clear_device_placement(device_row))

        zone_row = self._repository.get_zone_by_id(zone_id)
        if zone_row is None:
            raise LocationNotFoundError(f"No zone with id {zone_id}.")

        return _to_device(self._repository.place_device(device_row, zone_row))

    def list_devices(self, location_id: UUID, zone_id: UUID) -> list[Device]:
        """Devices in one zone. 404 territory if the zone is not in that location."""
        if self._repository.get_zone(location_id, zone_id) is None:
            raise LocationNotFoundError(f"No zone {zone_id} in location {location_id}.")

        return [_to_device(row) for row in self._repository.devices_in_zone(zone_id)]


def _to_device(row: DeviceRow) -> Device:
    return Device(
        id=row.id,
        device_type=row.device_type,
        role=row.role,
        device_family=row.device_family,
        display_name=row.display_name or "",
        default_config=dict(row.default_config or {}),
        zone_id=row.zone_id,
        location_id=row.location_id,
        # Phase 5. Without these two the placement response would report the
        # defaults for every device instead of what the row actually holds.
        sampling_interval_seconds=row.sampling_interval_seconds,
        tracking_enabled=row.tracking_enabled,
    )