from abc import ABC, abstractmethod

from src.domain.sensors.entity import Sensor

# A sensor made on its own is a software sensor. The families override this
# when they build a kit, so a Phase 3 edge probe still comes out as mqtt.
DEFAULT_PROTOCOL = "simulation"


class SensorCreator(ABC):
    @abstractmethod
    def create_sensor(self, display_name: str | None = None) -> Sensor:
        """Build an unsaved sensor carrying this type's defaults."""


class MoistureSensorCreator(SensorCreator):
    def create_sensor(self, display_name: str | None = None) -> Sensor:
        return Sensor(
            device_type="moisture_sensor",
            display_name=display_name or "Soil moisture sensor",
            # The interval appears twice on purpose. The column is what the
            # sampler reads; the copy in default_config is kept so the Phase 2
            # config stays readable on its own.
            sampling_interval_seconds=300,
            default_config={
                "unit": "vwc",
                "protocol": DEFAULT_PROTOCOL,
                "sampling_interval_seconds": 300,
                "moisture_threshold_percent": 35,
            },
        )


class LightSensorCreator(SensorCreator):
    def create_sensor(self, display_name: str | None = None) -> Sensor:
        return Sensor(
            device_type="light_sensor",
            display_name=display_name or "Ambient light sensor",
            sampling_interval_seconds=60,
            default_config={
                "unit": "lux",
                "protocol": DEFAULT_PROTOCOL,
                "sampling_interval_seconds": 60,
                "daylight_target_lux": 12000,
            },
        )


_CREATORS: dict[str, SensorCreator] = {
    "moisture": MoistureSensorCreator(),
    "light": LightSensorCreator(),
}


def available_sensor_types() -> list[str]:
    return sorted(_CREATORS)


def get_creator(sensor_type: str) -> SensorCreator:
    try:
        return _CREATORS[sensor_type]
    except KeyError:
        known = ", ".join(available_sensor_types())
        raise ValueError(f"Unknown sensor type '{sensor_type}'. Known types: {known}") from None