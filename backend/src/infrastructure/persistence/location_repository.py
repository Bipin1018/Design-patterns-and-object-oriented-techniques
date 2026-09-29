"""Persistence for locations, zones and device placement.

The only place that knows both the location domain and SQLAlchemy.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.domain.locations.entity import LocationConfig
from src.infrastructure.persistence.models import DeviceRow, LocationRow, ZoneRow


class LocationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- Step 5: create and read -------------------------------------------

    def save_config(self, config: LocationConfig) -> tuple[LocationRow, list[ZoneRow]]:
        """Write the location and all its zones as one transaction.

        flush() sends the location INSERT so PostgreSQL hands back its id,
        which the zones need, but does not end the transaction. One commit at
        the end means a failure rolls back the location as well as the zones,
        so a location can never end up stored with no zones.
        """
        location_row = LocationRow(name=config.location.name)
        self._session.add(location_row)
        self._session.flush()

        zone_rows = [
            ZoneRow(
                location_id=location_row.id,
                name=zone.name,
                moisture_threshold_low=zone.moisture_threshold_low,
                moisture_threshold_high=zone.moisture_threshold_high,
                schedule=zone.schedule,
            )
            for zone in config.location.zones
        ]
        self._session.add_all(zone_rows)
        self._session.commit()

        self._session.refresh(location_row)
        for row in zone_rows:
            self._session.refresh(row)
        return location_row, zone_rows

    def get_config(self, location_id: UUID) -> tuple[LocationRow, list[ZoneRow]] | None:
        """One location with its zones, or None if there is no such location."""
        location_row = self._session.get(LocationRow, location_id)
        if location_row is None:
            return None
        return location_row, self._zones_of(location_id)

    # -- Step 6a: list and delete ------------------------------------------

    def list_locations(self) -> list[LocationRow]:
        """Every location, newest first."""
        statement = select(LocationRow).order_by(LocationRow.created_at.desc())
        return list(self._session.execute(statement).scalars().all())

    def delete_location(self, location_id: UUID) -> bool:
        """Delete a location. False if it was not there.

        Zones go with it through ON DELETE CASCADE, and both device columns are
        cleared by their own ON DELETE SET NULL, so the device rows survive
        unplaced.
        """
        location_row = self._session.get(LocationRow, location_id)
        if location_row is None:
            return False
        self._session.delete(location_row)
        self._session.commit()
        return True

    # -- Step 6c: zones on a saved location --------------------------------

    def get_zone(self, location_id: UUID, zone_id: UUID) -> ZoneRow | None:
        """A zone, but only if it belongs to that location."""
        zone_row = self._session.get(ZoneRow, zone_id)
        if zone_row is None or zone_row.location_id != location_id:
            return None
        return zone_row

    def get_zone_by_id(self, zone_id: UUID) -> ZoneRow | None:
        """A zone by id alone, for placement where the location comes from the zone."""
        return self._session.get(ZoneRow, zone_id)

    def add_zone(
        self,
        location_id: UUID,
        name: str,
        low: float,
        high: float,
        schedule: dict[str, Any] | None = None,
    ) -> ZoneRow:
        zone_row = ZoneRow(
            location_id=location_id,
            name=name.strip(),
            moisture_threshold_low=low,
            moisture_threshold_high=high,
            schedule=schedule or {},
        )
        self._session.add(zone_row)
        self._session.commit()
        self._session.refresh(zone_row)
        return zone_row

    def update_zone(
        self,
        zone_row: ZoneRow,
        name: str,
        low: float,
        high: float,
        schedule: dict[str, Any] | None = None,
    ) -> ZoneRow:
        zone_row.name = name.strip()
        zone_row.moisture_threshold_low = low
        zone_row.moisture_threshold_high = high
        zone_row.schedule = schedule or {}
        self._session.commit()
        self._session.refresh(zone_row)
        return zone_row

    def count_zones(self, location_id: UUID) -> int:
        return len(self._zones_of(location_id))

    def delete_zone(self, zone_row: ZoneRow) -> None:
        """Delete a zone, unplacing its devices first.

        ON DELETE SET NULL only clears zone_id. location_id points at the
        location, which still exists, so the database leaves it set. Clearing
        both here is what stops a device claiming a location it is no longer in.
        """
        self.clear_devices_in_zone(zone_row.id)
        self._session.delete(zone_row)
        self._session.commit()

    # -- Step 6b: device placement -----------------------------------------

    def clear_devices_in_zone(self, zone_id: UUID) -> None:
        self._session.execute(
            update(DeviceRow).where(DeviceRow.zone_id == zone_id).values(zone_id=None, location_id=None)
        )

    def place_device(self, device_row: DeviceRow, zone_row: ZoneRow) -> DeviceRow:
        """Put a device in a zone, copying the location from the zone itself.

        The client never sends location_id, so the two columns cannot disagree.
        """
        device_row.zone_id = zone_row.id
        device_row.location_id = zone_row.location_id
        self._session.commit()
        self._session.refresh(device_row)
        return device_row

    def clear_device_placement(self, device_row: DeviceRow) -> DeviceRow:
        device_row.zone_id = None
        device_row.location_id = None
        self._session.commit()
        self._session.refresh(device_row)
        return device_row

    def get_device(self, device_id: UUID) -> DeviceRow | None:
        return self._session.get(DeviceRow, device_id)

    def devices_in_zone(self, zone_id: UUID) -> list[DeviceRow]:
        statement = (
            select(DeviceRow)
            .where(DeviceRow.zone_id == zone_id)
            .order_by(DeviceRow.created_at.desc())
        )
        return list(self._session.execute(statement).scalars().all())

    # -- internals ----------------------------------------------------------

    def _zones_of(self, location_id: UUID) -> list[ZoneRow]:
        statement = (
            select(ZoneRow)
            .where(ZoneRow.location_id == location_id)
            .order_by(ZoneRow.created_at)
        )
        return list(self._session.execute(statement).scalars().all())