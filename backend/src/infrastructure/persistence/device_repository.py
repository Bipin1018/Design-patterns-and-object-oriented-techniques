"""Maps domain objects to and from rows in the devices table.

This is the only place that knows both the domain entities and SQLAlchemy.
Phase 2's sensor methods stay so /api/sensors keeps working; Phase 3 adds the
device methods that handle sensors and actuators together; Phase 5 adds the
lookups the reading path and the sampler need.
"""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.domain.devices.entity import Device
from src.domain.sensors.entity import Sensor
from src.infrastructure.adapters.sensors.selector import PROTOCOL_SIMULATION
from src.infrastructure.persistence.models import DeviceRow

DEFAULT_FAMILY = "simulation"


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- Phase 2: sensors ---------------------------------------------------

    def save_sensor(self, sensor: Sensor) -> Sensor:
        """Write a sensor as a devices row and return it with its new id."""
        row = DeviceRow(
            device_type=sensor.device_type,
            role="sensor",
            # Phase 3 column. Set it here too so sensors created through the
            # old endpoint are never left without a family.
            device_family=DEFAULT_FAMILY,
            display_name=sensor.display_name,
            default_config=sensor.default_config,
            sampling_interval_seconds=sensor.sampling_interval_seconds,
            tracking_enabled=sensor.tracking_enabled,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_sensor(row)

    def list_sensors(self) -> list[Sensor]:
        """Every sensor row, newest first."""
        statement = (
            select(DeviceRow)
            .where(DeviceRow.role == "sensor")
            .order_by(DeviceRow.created_at.desc())
        )
        rows = self._session.execute(statement).scalars().all()
        return [self._to_sensor(row) for row in rows]

    # -- Phase 3: devices ---------------------------------------------------

    def save_device(self, device: Device) -> Device:
        """Write one device of any role."""
        row = self._to_row(device)
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_device(row)

    def save_devices(self, devices: list[Device]) -> list[Device]:
        """Write a whole kit in one transaction.

        One commit for the set, not one per device: a family is meant to be
        coherent, so a half-written kit is worse than none at all.
        """
        rows = [self._to_row(device) for device in devices]
        self._session.add_all(rows)
        self._session.commit()
        for row in rows:
            self._session.refresh(row)
        return [self._to_device(row) for row in rows]

    def list_devices(
        self,
        *,
        device_family: str | None = None,
        role: str | None = None,
    ) -> list[Device]:
        """Devices, newest first, narrowed by family and role when given."""
        statement = select(DeviceRow)
        if device_family is not None:
            statement = statement.where(DeviceRow.device_family == device_family)
        if role is not None:
            statement = statement.where(DeviceRow.role == role)
        statement = statement.order_by(DeviceRow.created_at.desc())

        rows = self._session.execute(statement).scalars().all()
        return [self._to_device(row) for row in rows]

    # -- Phase 5: reading and sampling --------------------------------------

    def get_device(self, device_id: UUID) -> Device | None:
        """One device by id, or None. The reading path starts here."""
        row = self._session.get(DeviceRow, device_id)
        return None if row is None else self._to_device(row)

    def list_sampling_candidates(self) -> list[Device]:
        """The sensors the simulation sampler is allowed to record.

        Three filters, and each one earns its place. role, because actuators
        are told things, not asked. tracking_enabled, because the user turned
        this device off. protocol, because an MQTT device publishes when it
        wants to, so generating a value for it here would be inventing data the
        device never sent.

        The IS NULL arm catches any row written before the Phase 5 migration
        gave every device a protocol. There should be none, but a missing key
        should mean "software sensor", not "silently skipped".
        """
        statement = (
            select(DeviceRow)
            .where(DeviceRow.role == "sensor")
            .where(DeviceRow.tracking_enabled.is_(True))
            .where(
                or_(
                    DeviceRow.default_config["protocol"].astext == PROTOCOL_SIMULATION,
                    DeviceRow.default_config["protocol"].astext.is_(None),
                )
            )
            .order_by(DeviceRow.created_at)
        )
        rows = self._session.execute(statement).scalars().all()
        return [self._to_device(row) for row in rows]

    def update_sampling(
        self,
        device_id: UUID,
        *,
        sampling_interval_seconds: int,
        tracking_enabled: bool,
    ) -> Device | None:
        """Write both sampling columns. None if there is no such device."""
        row = self._session.get(DeviceRow, device_id)
        if row is None:
            return None

        row.sampling_interval_seconds = sampling_interval_seconds
        row.tracking_enabled = tracking_enabled
        self._session.commit()
        self._session.refresh(row)
        return self._to_device(row)

    # -- Row mapping --------------------------------------------------------

    @staticmethod
    def _to_row(device: Device) -> DeviceRow:
        return DeviceRow(
            device_type=device.device_type,
            role=device.role,
            device_family=device.device_family,
            display_name=device.display_name,
            default_config=device.default_config,
            sampling_interval_seconds=device.sampling_interval_seconds,
            tracking_enabled=device.tracking_enabled,
        )

    @staticmethod
    def _to_device(row: DeviceRow) -> Device:
        return Device(
            id=row.id,
            device_type=row.device_type,
            role=row.role,
            device_family=row.device_family,
            display_name=row.display_name or "",
            default_config=dict(row.default_config or {}),
            zone_id=row.zone_id,
            location_id=row.location_id,
            sampling_interval_seconds=row.sampling_interval_seconds,
            tracking_enabled=row.tracking_enabled,
        )

    @staticmethod
    def _to_sensor(row: DeviceRow) -> Sensor:
        return Sensor(
            id=row.id,
            device_type=row.device_type,
            display_name=row.display_name or "",
            default_config=dict(row.default_config or {}),
            sampling_interval_seconds=row.sampling_interval_seconds,
            tracking_enabled=row.tracking_enabled,
        )