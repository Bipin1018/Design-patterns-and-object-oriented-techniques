"""Unit tests for the location config builder.

No database, no HTTP, and no assignment service: the builder is domain code,
so it stands on its own.
"""

import pytest

from src.domain.locations.config_builder import LocationConfigBuilder
from src.domain.locations.errors import ConfigurationError


def test_build_success() -> None:
    config = (
        LocationConfigBuilder()
        .with_location_name("Lab Site A")
        .add_zone("Bench 1", 0.2, 0.45, {"watering": "08:00"})
        .add_zone("Bench 2", 0.25, 0.5)
        .build()
    )

    assert config.location.name == "Lab Site A"
    assert len(config.location.zones) == 2
    assert config.location.id is None  # not saved yet
    assert all(zone.id is None for zone in config.location.zones)
    assert config.location.zones[0].schedule == {"watering": "08:00"}


def test_build_requires_name() -> None:
    with pytest.raises(ConfigurationError, match="name is required"):
        LocationConfigBuilder().add_zone("Bench 1", 0.2, 0.45).build()


def test_build_rejects_blank_name() -> None:
    with pytest.raises(ConfigurationError):
        LocationConfigBuilder().with_location_name("   ").add_zone("Bench 1", 0.2, 0.45).build()


def test_build_requires_zones() -> None:
    with pytest.raises(ConfigurationError, match="at least one zone"):
        LocationConfigBuilder().with_location_name("Lab Site A").build()


def test_build_rejects_invalid_thresholds() -> None:
    with pytest.raises(ConfigurationError, match="must be below"):
        LocationConfigBuilder().with_location_name("A").add_zone("Z", 0.5, 0.2).build()


def test_build_rejects_thresholds_outside_range() -> None:
    with pytest.raises(ConfigurationError, match="outside"):
        LocationConfigBuilder().with_location_name("A").add_zone("Z", 0.2, 45).build()


def test_build_rejects_duplicate_zone_names() -> None:
    with pytest.raises(ConfigurationError, match="used twice"):
        (
            LocationConfigBuilder()
            .with_location_name("A")
            .add_zone("Bench 1", 0.2, 0.4)
            .add_zone("bench 1", 0.3, 0.5)
            .build()
        )


def test_builder_has_no_way_to_attach_a_device() -> None:
    """Placement happens after the zone has an id, so it is not on the builder."""
    assert not hasattr(LocationConfigBuilder(), "add_device")