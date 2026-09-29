"""Builder for a location configuration.

Parts go in one at a time, and nothing is checked until build() runs. That is
the point of the pattern here: a location with three zones has too many pieces
to pass to one constructor, and the rules only make sense once every piece is
present.

The builder has no add_device method on purpose. A zone has no id until it is
saved, and devices already exist from earlier phases, so assignment is a
separate update afterwards.
"""

from typing import Any

from src.domain.locations.entity import Location, LocationConfig, Zone
from src.domain.locations.errors import ConfigurationError

# Volumetric water content runs 0.0 to 1.0 in this product.
THRESHOLD_MIN = 0.0
THRESHOLD_MAX = 1.0


class LocationConfigBuilder:
    def __init__(self) -> None:
        self._location_name: str = ""
        self._zones: list[Zone] = []

    def with_location_name(self, name: str) -> "LocationConfigBuilder":
        """Set the location name. Returns self so calls can be chained."""
        self._location_name = name
        return self

    def add_zone(
        self,
        name: str,
        moisture_threshold_low: float,
        moisture_threshold_high: float,
        schedule: dict[str, Any] | None = None,
    ) -> "LocationConfigBuilder":
        """Add one zone. Nothing is checked until build() runs."""
        self._zones.append(
            Zone(
                name=name,
                moisture_threshold_low=moisture_threshold_low,
                moisture_threshold_high=moisture_threshold_high,
                schedule=schedule or {},
            )
        )
        return self

    def build(self) -> LocationConfig:
        """Check every rule, then return the finished config.

        Raises ConfigurationError if anything is wrong, so an invalid config
        can never reach the repository.
        """
        name = self._location_name.strip()
        if not name:
            raise ConfigurationError("Location name is required.")

        if not self._zones:
            raise ConfigurationError("A location needs at least one zone.")

        seen: set[str] = set()
        for zone in self._zones:
            validate_zone_fields(
                zone.name, zone.moisture_threshold_low, zone.moisture_threshold_high
            )
            key = zone.name.strip().lower()
            if key in seen:
                raise ConfigurationError(f"Zone name '{zone.name.strip()}' is used twice.")
            seen.add(key)

        zones = tuple(
            Zone(
                name=zone.name.strip(),
                moisture_threshold_low=zone.moisture_threshold_low,
                moisture_threshold_high=zone.moisture_threshold_high,
                schedule=dict(zone.schedule),
            )
            for zone in self._zones
        )
        return LocationConfig(location=Location(name=name, zones=zones))


def validate_zone_fields(name: str, low: float, high: float) -> None:
    """The zone rules, on their own.

    Adding or editing a zone on a saved location must not call build(), but it
    must apply the same rules, so they live in a function both can use.
    """
    if not name or not name.strip():
        raise ConfigurationError("Zone name is required.")

    for label, value in (("low", low), ("high", high)):
        if not THRESHOLD_MIN <= value <= THRESHOLD_MAX:
            raise ConfigurationError(
                f"Zone '{name.strip()}': {label} threshold {value} is outside "
                f"{THRESHOLD_MIN}–{THRESHOLD_MAX}."
            )

    if low >= high:
        raise ConfigurationError(
            f"Zone '{name.strip()}': low threshold {low} must be below high threshold {high}."
        )