"""Factory Method for sensors."""

from abc import ABC, abstractmethod

from src.domain.sensors.entity import Sensor


class SensorCreator(ABC):
    """The creator interface. Callers depend on this, never on a subclass."""

    @abstractmethod
    def create_sensor(self, display_name: str | None = None) -> Sensor:
        """Build an unsaved sensor carrying this type's defaults."""


class MoistureSensorCreator(SensorCreator):
    """Soil moisture probe: volumetric water content, sampled slowly."""

    def create_sensor(self, display_name: str | None = None) -> Sensor:
        return Sensor(
            device_type="moisture_sensor",
            display_name=display_name or "Soil moisture sensor",
            default_config={
                "unit": "vwc",
                "sampling_interval_seconds": 300,
                "moisture_threshold_percent": 35,
            },
        )


class LightSensorCreator(SensorCreator):
    """Light sensor: lux, sampled far more often than soil moisture."""

    def create_sensor(self, display_name: str | None = None) -> Sensor:
        return Sensor(
            device_type="light_sensor",
            display_name=display_name or "Ambient light sensor",
            default_config={
                "unit": "lux",
                "sampling_interval_seconds": 60,
                "daylight_target_lux": 12000,
            },
        )


_CREATORS: dict[str, SensorCreator] = {
    "moisture": MoistureSensorCreator(),
    "light": LightSensorCreator(),
}


def available_sensor_types() -> list[str]:
    """Keys accepted by get_creator, for error messages and API docs."""
    return sorted(_CREATORS)


def get_creator(sensor_type: str) -> SensorCreator:
    """Look up a creator by short key. Raises ValueError on an unknown key."""
    try:
        return _CREATORS[sensor_type]
    except KeyError:
        known = ", ".join(available_sensor_types())
        raise ValueError(f"Unknown sensor type '{sensor_type}'. Known types: {known}") from None