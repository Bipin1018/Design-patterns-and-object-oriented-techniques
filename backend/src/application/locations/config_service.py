"""Use cases for location configuration.

build_and_save is the only one that touches the builder. Listing, deleting and
zone management are separate operations on data that already exists, so they
reuse the zone rules directly instead of rebuilding the location.
"""

from typing import Any
from uuid import UUID

from src.application.locations.dto import (
    BuildLocationConfigRequestDto,
    LocationConfigDto,
    LocationSummaryDto,
    ZoneDto,
    ZoneInputDto,
)
from src.application.locations.mappers import (
    location_config_to_dto,
    location_to_summary_dto,
    zone_to_dto,
)
from src.domain.locations.config_builder import LocationConfigBuilder, validate_zone_fields
from src.domain.locations.errors import ConfigurationError
from src.infrastructure.persistence.location_repository import LocationRepository


class LocationNotFoundError(LookupError):
    """No location or zone with that id."""


class LocationConfigService:
    def __init__(self, repository: LocationRepository) -> None:
        self._repository = repository

    # -- Step 5 -------------------------------------------------------------

    def build_and_save(self, request: BuildLocationConfigRequestDto) -> LocationConfigDto:
        """Feed the request through the builder, then save what it returns."""
        builder = LocationConfigBuilder().with_location_name(request.location_name)
        for zone in request.zones:
            builder.add_zone(
                zone.name,
                zone.moisture_threshold_low,
                zone.moisture_threshold_high,
                zone.schedule,
            )
        config = builder.build()  # raises ConfigurationError before any write

        location_row, zone_rows = self._repository.save_config(config)
        return location_config_to_dto(location_row, zone_rows)

    def get_config(self, location_id: UUID) -> LocationConfigDto:
        found = self._repository.get_config(location_id)
        if found is None:
            raise LocationNotFoundError(f"No location with id {location_id}.")
        return location_config_to_dto(*found)

    # -- Step 6a ------------------------------------------------------------

    def list_locations(self) -> list[LocationSummaryDto]:
        return [location_to_summary_dto(row) for row in self._repository.list_locations()]

    def delete_location(self, location_id: UUID) -> None:
        if not self._repository.delete_location(location_id):
            raise LocationNotFoundError(f"No location with id {location_id}.")

    # -- Step 6c ------------------------------------------------------------

    def add_zone(self, location_id: UUID, zone: ZoneInputDto) -> ZoneDto:
        if self._repository.get_config(location_id) is None:
            raise LocationNotFoundError(f"No location with id {location_id}.")

        validate_zone_fields(zone.name, zone.moisture_threshold_low, zone.moisture_threshold_high)
        row = self._repository.add_zone(
            location_id,
            zone.name,
            zone.moisture_threshold_low,
            zone.moisture_threshold_high,
            zone.schedule,
        )
        return zone_to_dto(row)

    def update_zone(self, location_id: UUID, zone_id: UUID, zone: ZoneInputDto) -> ZoneDto:
        row = self._require_zone(location_id, zone_id)

        # Checked before the write, so a rejected update leaves the row alone.
        validate_zone_fields(zone.name, zone.moisture_threshold_low, zone.moisture_threshold_high)
        updated = self._repository.update_zone(
            row,
            zone.name,
            zone.moisture_threshold_low,
            zone.moisture_threshold_high,
            zone.schedule,
        )
        return zone_to_dto(updated)

    def delete_zone(self, location_id: UUID, zone_id: UUID) -> None:
        row = self._require_zone(location_id, zone_id)

        if self._repository.count_zones(location_id) <= 1:
            raise ConfigurationError("A location must keep at least one zone.")

        self._repository.delete_zone(row)

    # -- internals ----------------------------------------------------------

    def _require_zone(self, location_id: UUID, zone_id: UUID) -> Any:
        row = self._repository.get_zone(location_id, zone_id)
        if row is None:
            raise LocationNotFoundError(f"No zone {zone_id} in location {location_id}.")
        return row