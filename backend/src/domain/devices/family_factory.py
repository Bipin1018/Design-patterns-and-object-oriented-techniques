"""Abstract Factory for device families.

Factory Method (Phase 2) answers "which single sensor do I build?". This answers
a different question: "which whole kit belongs together?".

A greenhouse runs either against simulated devices or against edge hardware.
Mixing the two makes no sense: a simulated pump cannot be driven by a GPIO pin.
Each family factory therefore returns one coherent set, and the sensors in that
set are still built by the Phase 2 creators rather than duplicated here.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.domain.devices.entity import Device
from src.domain.sensors.creators import get_creator
from src.domain.sensors.entity import Sensor


class DeviceFamilyFactory(ABC):
    """Returns a matching set of devices for one environment."""

    @property
    @abstractmethod
    def family_key(self) -> str:
        """Short key stored on every device this factory builds."""

    @abstractmethod
    def create_device_set(self) -> list[Device]:
        """Two sensors and two actuators that belong together."""


def _sensor_as_device(sensor: Sensor, *, family: str, label: str, extra: dict[str, Any]) -> Device:
    """Turn a Phase 2 Sensor into a Device tagged with its family."""
    return Device(
        device_type=sensor.device_type,
        role="sensor",
        device_family=family,
        display_name=label,
        default_config={**sensor.default_config, **extra},
    )


class SimulationDeviceFactory(DeviceFamilyFactory):
    """Everything fake: no hardware, values generated in software."""

    @property
    def family_key(self) -> str:
        return "simulation"

    def create_device_set(self) -> list[Device]:
        shared = {"protocol": "sim"}
        return [
            _sensor_as_device(
                get_creator("moisture").create_sensor(),
                family=self.family_key,
                label="Sim soil moisture sensor",
                extra=shared,
            ),
            _sensor_as_device(
                get_creator("light").create_sensor(),
                family=self.family_key,
                label="Sim ambient light sensor",
                extra=shared,
            ),
            Device(
                device_type="water_pump",
                role="actuator",
                device_family=self.family_key,
                display_name="Sim irrigation pump",
                default_config={
                    "protocol": "sim",
                    "flow_litres_per_minute": 4.5,
                    "max_runtime_seconds": 600,
                },
            ),
            Device(
                device_type="grow_light",
                role="actuator",
                device_family=self.family_key,
                display_name="Sim grow light",
                default_config={
                    "protocol": "sim",
                    "channels": 2,
                    "max_brightness_percent": 100,
                },
            ),
        ]


class EdgeHardwareFactory(DeviceFamilyFactory):
    """Stub hardware kit: same shape, wired to pins instead of software."""

    @property
    def family_key(self) -> str:
        return "edge"

    def create_device_set(self) -> list[Device]:
        return [
            _sensor_as_device(
                get_creator("moisture").create_sensor(),
                family=self.family_key,
                label="Edge soil moisture probe",
                extra={"protocol": "gpio-stub", "gpio_pin": 4},
            ),
            _sensor_as_device(
                get_creator("light").create_sensor(),
                family=self.family_key,
                label="Edge ambient light probe",
                extra={"protocol": "gpio-stub", "i2c_address": "0x23"},
            ),
            Device(
                device_type="water_pump",
                role="actuator",
                device_family=self.family_key,
                display_name="Edge relay pump",
                default_config={
                    "protocol": "gpio-stub",
                    "gpio_pin": 17,
                    "flow_litres_per_minute": 2.0,
                    "max_runtime_seconds": 300,
                },
            ),
            Device(
                device_type="grow_light",
                role="actuator",
                device_family=self.family_key,
                display_name="Edge LED driver",
                default_config={
                    "protocol": "gpio-stub",
                    "gpio_pin": 27,
                    "channels": 4,
                    "max_brightness_percent": 80,
                },
            ),
        ]


_FAMILIES: dict[str, DeviceFamilyFactory] = {
    "simulation": SimulationDeviceFactory(),
    "edge": EdgeHardwareFactory(),
}


def available_families() -> list[str]:
    """Family keys accepted by get_family_factory."""
    return sorted(_FAMILIES)


def get_family_factory(family: str) -> DeviceFamilyFactory:
    """Look up a family factory. Raises ValueError on an unknown key."""
    try:
        return _FAMILIES[family]
    except KeyError:
        known = ", ".join(available_families())
        raise ValueError(f"Unknown device family '{family}'. Known families: {known}") from None