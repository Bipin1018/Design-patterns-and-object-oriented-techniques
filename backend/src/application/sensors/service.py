

from src.domain.sensors.creators import get_creator
from src.domain.sensors.entity import Sensor
from src.infrastructure.persistence.device_repository import DeviceRepository


class SensorService:
    def __init__(self, repository: DeviceRepository) -> None:
        self._repository = repository

    def create_sensor(self, sensor_type: str, display_name: str | None = None) -> Sensor:
        """Ask the right creator for a sensor, then persist it.

        get_creator raises ValueError on an unknown type, so a bad request
        never reaches the database.
        """
        creator = get_creator(sensor_type)
        prototype = creator.create_sensor(display_name=display_name)
        return self._repository.save_sensor(prototype)

    def list_sensors(self) -> list[Sensor]:
        return self._repository.list_sensors()