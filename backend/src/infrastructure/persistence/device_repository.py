
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.sensors.entity import Sensor
from src.infrastructure.persistence.models import DeviceRow


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_sensor(self, sensor: Sensor) -> Sensor:
        """Write the sensor as a devices row and return it with its new id."""
        row = DeviceRow(
            device_type=sensor.device_type,
            role="sensor",
            display_name=sensor.display_name,
            default_config=sensor.default_config,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_entity(row)

    def list_sensors(self) -> list[Sensor]:
        """Every sensor row, newest first."""
        statement = (
            select(DeviceRow)
            .where(DeviceRow.role == "sensor")
            .order_by(DeviceRow.created_at.desc())
        )
        rows = self._session.execute(statement).scalars().all()
        return [self._to_entity(row) for row in rows]

    @staticmethod
    def _to_entity(row: DeviceRow) -> Sensor:
        return Sensor(
            id=row.id,
            device_type=row.device_type,
            display_name=row.display_name or "",
            default_config=dict(row.default_config or {}),
        )