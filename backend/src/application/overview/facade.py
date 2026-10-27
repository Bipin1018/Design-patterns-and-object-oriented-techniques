"""One entry point for everything the dashboard overview shows."""

from collections import defaultdict
from uuid import UUID

from src.application.automation.service import AutomationService
from src.application.locations.config_service import LocationNotFoundError
from src.application.locations.dto import LocationSummaryDto
from src.application.overview.dto import (
    DeviceCountsDto,
    LocationOverviewDto,
    OverviewDeviceDto,
    OverviewReadingDto,
    OverviewZoneDto,
    RecommendationDto,
)
from src.infrastructure.persistence.overview_repository import (
    AssignedDevice,
    NewestReading,
    OverviewRepository,
    OverviewZone,
)

SENSOR_ROLE = "sensor"
ACTUATOR_ROLE = "actuator"


class LocationOverviewFacade:
    def __init__(self, overview: OverviewRepository, automation: AutomationService) -> None:
        self._overview = overview
        self._automation = automation

    def get_overview(self, location_id: UUID) -> LocationOverviewDto:
        location = self._overview.location_with_zones(location_id)
        if location is None:
            raise LocationNotFoundError(f"No location with id {location_id}.")

        devices = self._overview.assigned_devices(location_id)
        readings = self._overview.newest_readings([device.id for device in devices])
        strategy_key, recommendation = self._strategy(location_id)

        by_zone: dict[UUID, list[AssignedDevice]] = defaultdict(list)
        for device in devices:
            by_zone[device.zone_id].append(device)

        return LocationOverviewDto(
            location=LocationSummaryDto(id=location.id, name=location.name),
            device_counts=DeviceCountsDto(
                sensor=sum(1 for device in devices if device.role == SENSOR_ROLE),
                actuator=sum(1 for device in devices if device.role == ACTUATOR_ROLE),
            ),
            zones=[
                self._zone(zone, by_zone.get(zone.id, []), readings)
                for zone in location.zones
            ],
            strategy_key=strategy_key,
            last_recommendation=recommendation,
        )

    def _strategy(self, location_id: UUID) -> tuple[str | None, RecommendationDto | None]:
        rule = self._automation.get_rule(location_id)
        if not rule.persisted:
            return None, None
        evaluation = self._automation.evaluate(location_id)
        return evaluation.strategy_key, RecommendationDto(
            action=evaluation.action,
            reason=evaluation.reason,
        )

    @staticmethod
    def _zone(
        zone: OverviewZone,
        devices: list[AssignedDevice],
        readings: dict[UUID, NewestReading],
    ) -> OverviewZoneDto:
        return OverviewZoneDto(
            id=zone.id,
            name=zone.name,
            moisture_threshold_low=zone.moisture_threshold_low,
            moisture_threshold_high=zone.moisture_threshold_high,
            devices=[
                OverviewDeviceDto(
                    id=device.id,
                    device_type=device.device_type,
                    role=device.role,
                    display_name=device.display_name,
                )
                for device in devices
            ],
            latest_readings=[
                OverviewReadingDto(
                    device_id=device.id,
                    value=readings[device.id].value,
                    unit=readings[device.id].unit,
                    recorded_at=readings[device.id].recorded_at,
                    tracking_enabled=device.tracking_enabled,
                    sampling_interval_seconds=device.sampling_interval_seconds,
                )
                for device in devices
                if device.id in readings
            ],
        )