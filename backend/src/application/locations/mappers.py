"""ORM rows -> DTOs.

Mapping lives here, not on the entities and not in the router.

The thresholds are Numeric in PostgreSQL, so SQLAlchemy returns them as
Decimal. float() is what keeps the JSON numeric instead of a string.
"""

from src.application.locations.dto import LocationConfigDto, LocationSummaryDto, ZoneDto
from src.infrastructure.persistence.models import LocationRow, ZoneRow


def location_to_summary_dto(row: LocationRow) -> LocationSummaryDto:
    return LocationSummaryDto(id=row.id, name=row.name)


def zone_to_dto(row: ZoneRow) -> ZoneDto:
    return ZoneDto(
        id=row.id,
        location_id=row.location_id,
        name=row.name,
        moisture_threshold_low=float(row.moisture_threshold_low),
        moisture_threshold_high=float(row.moisture_threshold_high),
        schedule=dict(row.schedule or {}),
    )


def location_config_to_dto(
    location_row: LocationRow,
    zone_rows: list[ZoneRow],
) -> LocationConfigDto:
    return LocationConfigDto(
        location=location_to_summary_dto(location_row),
        zones=[zone_to_dto(row) for row in zone_rows],
    )