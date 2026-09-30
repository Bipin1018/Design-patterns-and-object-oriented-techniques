"""Reading ingest: the only writer of sensor_readings.

Three ways in, one way through:

    POST /api/sensors/{id}/read   -> take_reading  -> select adapter, ask it
    the simulation sampler        -> take_reading  -> same
    Phase 12 MQTT or device HTTP  -> record        -> already translated

They converge here on purpose. Phase 11 publishes reading.created from this
class, and it can only promise "every reading raises an event" because every
reading passes through this one place.

take_reading never looks at tracking_enabled. Turning tracking off means "stop
sampling this device", not "stop me reading it myself". The sampler is what
honours the flag.
"""

from uuid import UUID

from src.application.readings.dto import ReadingDto
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
    ) -> None:
        self._devices = devices
        self._readings = readings

    def take_reading(self, device_id: UUID) -> ReadingDto:
        """Ask this device's adapter for a value, store it, return the DTO.

        The adapter is chosen by the selector, so this method never names a
        concrete adapter class. Adding a protocol changes the selector and
        nothing here.
        """
        device = self._devices.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(f"No device with id {device_id}.")

        port = get_sensor_port(device)  # raises AdapterError -> 400
        reading = port.read(device)
        return _to_dto(self._readings.insert(reading))

    def record(self, device_id: UUID, reading: Reading) -> ReadingDto:
        """Store a reading that was translated somewhere else.

        Phase 12's MQTT subscriber and device HTTP route call this. The device
        is still loaded first, so a message quoting an unknown id is rejected
        rather than stored against nothing.
        """
        device = self._devices.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(f"No device with id {device_id}.")

        return _to_dto(self._readings.insert(reading))

    def list_readings(self, device_id: UUID, limit: int = 20) -> list[ReadingDto]:
        """Recent readings for a device, newest first."""
        device = self._devices.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(f"No device with id {device_id}.")

        return [_to_dto(reading) for reading in self._readings.list_for_device(device_id, limit)]


def _to_dto(reading: Reading) -> ReadingDto:
    return ReadingDto(
        device_id=reading.device_id,
        value=reading.value,
        unit=reading.unit,
        source=reading.source,
        recorded_at=reading.recorded_at,
    )