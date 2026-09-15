"""Unit tests for the sensor creators.

No database, no web server: the domain has no infrastructure dependencies,
so these run on their own.
"""

import pytest

from src.domain.sensors.creators import (
    LightSensorCreator,
    MoistureSensorCreator,
    available_sensor_types,
    get_creator,
)


def test_moisture_creator_defaults() -> None:
    sensor = MoistureSensorCreator().create_sensor()

    assert sensor.device_type == "moisture_sensor"
    assert sensor.default_config["moisture_threshold_percent"] == 35
    assert sensor.default_config["unit"] == "vwc"
    assert sensor.id is None  # not saved yet


def test_light_creator_defaults() -> None:
    sensor = LightSensorCreator().create_sensor()

    assert sensor.device_type == "light_sensor"
    assert sensor.default_config["unit"] == "lux"
    assert "moisture_threshold_percent" not in sensor.default_config


def test_creators_produce_different_configs() -> None:
    moisture = MoistureSensorCreator().create_sensor()
    light = LightSensorCreator().create_sensor()

    assert moisture.default_config != light.default_config
    assert (
        moisture.default_config["sampling_interval_seconds"]
        != light.default_config["sampling_interval_seconds"]
    )


def test_display_name_can_be_overridden() -> None:
    assert MoistureSensorCreator().create_sensor("Bed 3 probe").display_name == "Bed 3 probe"
    assert MoistureSensorCreator().create_sensor().display_name == "Soil moisture sensor"


def test_registry_returns_the_right_creator() -> None:
    assert get_creator("moisture").create_sensor().device_type == "moisture_sensor"
    assert get_creator("light").create_sensor().device_type == "light_sensor"
    assert available_sensor_types() == ["light", "moisture"]


def test_unknown_type_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown sensor type"):
        get_creator("temperature")


def test_each_sensor_gets_its_own_config_dict() -> None:
    first = MoistureSensorCreator().create_sensor()
    second = MoistureSensorCreator().create_sensor()

    first.default_config["unit"] = "changed"

    assert second.default_config["unit"] == "vwc"