
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.application.sensors.service import SensorService
from src.domain.sensors.creators import available_sensor_types
from src.domain.sensors.entity import Sensor
from src.infrastructure.db import get_db
from src.infrastructure.persistence.device_repository import DeviceRepository

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


class CreateSensorRequest(BaseModel):
    type: str = Field(description="Creator key: moisture or light.")
    display_name: str | None = Field(default=None, description="Optional label.")


class SensorResponse(BaseModel):
    id: UUID
    device_type: str
    display_name: str
    default_config: dict[str, Any]


def get_service(session: Session = Depends(get_db)) -> SensorService:
    """Build the service for one request, wired to that request's session."""
    return SensorService(DeviceRepository(session))


def _to_response(sensor: Sensor) -> SensorResponse:
    return SensorResponse(
        id=sensor.id,
        device_type=sensor.device_type,
        display_name=sensor.display_name,
        default_config=sensor.default_config,
    )


@router.get("", response_model=list[SensorResponse], summary="List sensors")
def list_sensors(service: SensorService = Depends(get_service)) -> list[SensorResponse]:
    return [_to_response(sensor) for sensor in service.list_sensors()]


@router.post(
    "",
    response_model=SensorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a sensor",
    description=f"Valid type keys: {', '.join(available_sensor_types())}.",
)
def create_sensor(
    payload: CreateSensorRequest,
    service: SensorService = Depends(get_service),
) -> SensorResponse:
    try:
        sensor = service.create_sensor(payload.type, payload.display_name)
    except ValueError as exc:
        # get_creator rejected the key, so nothing was written.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(sensor)