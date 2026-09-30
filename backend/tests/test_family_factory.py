"""Unit tests for the device family factories.

No database and no HTTP: the domain has no infrastructure dependencies, so
these run on their own.
"""

import pytest

from src.domain.devices.family_factory import (
    EdgeHardwareFactory,
    SimulationDeviceFactory,
    available_families,
    get_family_factory,
)


def test_simulation_factory_returns_four_devices() -> None:
    kit = SimulationDeviceFactory().create_device_set()

    assert len(kit) == 4
    assert {device.device_family for device in kit} == {"simulation"}
    assert {device.role for device in kit} == {"sensor", "actuator"}


def test_simulation_kit_has_two_sensors_and_two_actuators() -> None:
    kit = SimulationDeviceFactory().create_device_set()

    assert len([d for d in kit if d.role == "sensor"]) == 2
    assert len([d for d in kit if d.role == "actuator"]) == 2


def test_edge_factory_differs_from_simulation() -> None:
    sim = SimulationDeviceFactory().create_device_set()
    edge = EdgeHardwareFactory().create_device_set()

    assert {d.device_family for d in edge} == {"edge"}
    assert sim[0].default_config["protocol"] != edge[0].default_config["protocol"]
    assert [d.display_name for d in sim] != [d.display_name for d in edge]


def test_families_compose_the_phase_two_creators() -> None:
    """Sensor defaults still come from the Factory Method creators."""
    kit = SimulationDeviceFactory().create_device_set()
    moisture = next(d for d in kit if d.device_type == "moisture_sensor")
    light = next(d for d in kit if d.device_type == "light_sensor")

    assert moisture.default_config["unit"] == "vwc"
    assert moisture.default_config["protocol"] == "simulation"  # set by the family
    # Phase 5: the creator's interval reaches the column, not just the JSON.
    assert moisture.sampling_interval_seconds == 300
    assert light.sampling_interval_seconds == 60


def test_edge_kit_reports_over_mqtt() -> None:
    """Phase 5 renamed the edge protocol, so the selector skips these devices."""
    kit = EdgeHardwareFactory().create_device_set()

    assert {d.default_config["protocol"] for d in kit} == {"mqtt"}


def test_devices_are_unsaved_before_the_repository_runs() -> None:
    assert all(device.id is None for device in SimulationDeviceFactory().create_device_set())


def test_registry_returns_the_right_factory() -> None:
    assert get_family_factory("simulation").family_key == "simulation"
    assert get_family_factory("edge").family_key == "edge"
    assert available_families() == ["edge", "simulation"]


def test_unknown_family_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown device family"):
        get_family_factory("greenhouse42")