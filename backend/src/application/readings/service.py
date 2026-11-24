"""Reading ingest: the only place that saves sensor readings.

Three ways in, one way through:

    POST /api/sensors/{id}/read   -> take_reading  -> ask the adapter
    the simulation sampler        -> take_reading  -> same
    Phase 12 MQTT or device HTTP  -> record        -> already translated

Because every reading passes through here, this is also the only place that
publishes reading.created. The sampler and the routes never publish.

Turning tracking off stops the sampler, not manual reads. A reading from an
untracked device is still saved, but no event is published for it.
"""

from uuid import UUID

from src.application.readings.dto import ReadingDto
from src.domain.devices.entity import Device
from src.domain.events.bus import EventBus
from src.domain.events.events import ReadingCreated
from src.domain.sensors.reading import Reading
from src.infrastructure.adapters.sensors.selector import get_sensor_port
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.reading_repository import ReadingRepository


class DeviceNotFoundError(LookupError):
    """No device with that id. The router turns this into a 404."""


class ReadingIngest:
    def __init__(
        self,
        devices: DeviceRepository,
        readings: ReadingRepository,
        bus: EventBus,
    ) -> None:
        self._devices = devices
        self._readings = readings
        self._bus = bus

    def take_reading(self, device_id: UUID) -> ReadingDto:
        """Ask this device's adapter for a value, save it, return it."""
        device = self._devices.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(f"No device with id {device_id}.")

        port = get_sensor_port(device)  # raises AdapterError -> 400
        reading = port.read(device)
        return self._store(device, reading)

    def record(self, device_id: UUID, reading: Reading) -> ReadingDto:
        """Save a reading that was already translated (MQTT, device HTTP).

        The device is loaded first, so an unknown id is rejected.
        """
        device = self._devices.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(f"No device with id {device_id}.")

        return self._store(device, reading)

    def list_readings(self, device_id: UUID, limit: int = 20) -> list[ReadingDto]:
        """Recent readings for a device, newest first."""
        device = self._devices.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(f"No device with id {device_id}.")

        return [_to_dto(reading) for reading in self._readings.list_for_device(device_id, limit)]

    def _store(self, device: Device, reading: Reading) -> ReadingDto:
        """Save the reading, then publish it if the device is tracked."""
        stored = self._readings.insert(reading)  # commits first

        if device.tracking_enabled:
            self._bus.publish(
                ReadingCreated(
                    device_id=stored.device_id,
                    location_id=device.location_id,  # None if the device has no zone
                    zone_id=device.zone_id,
                    value=stored.value,
                    unit=stored.unit,
                    source=stored.source,
                    recorded_at=stored.recorded_at,
                )
            )

        return _to_dto(stored)


def _to_dto(reading: Reading) -> ReadingDto:
    return ReadingDto(
        device_id=reading.device_id,
        value=reading.value,
        unit=reading.unit,
        source=reading.source,
        recorded_at=reading.recorded_at,
    )