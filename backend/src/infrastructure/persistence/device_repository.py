
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.devices.entity import Device
from src.domain.sensors.entity import Sensor
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

    # -- Row mapping --------------------------------------------------------

    @staticmethod
    def _to_row(device: Device) -> DeviceRow:
        return DeviceRow(
            device_type=device.device_type,
            role=device.role,
            device_family=device.device_family,
            display_name=device.display_name,
            default_config=device.default_config,
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
        )

    @staticmethod
    def _to_sensor(row: DeviceRow) -> Sensor:
        return Sensor(
            id=row.id,
            device_type=row.device_type,
            display_name=row.display_name or "",
            default_config=dict(row.default_config or {}),
        )