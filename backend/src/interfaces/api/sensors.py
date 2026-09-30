"""HTTP routes for sensors.

The router stays thin: read the request, call the service, map the result to
JSON. It never names a concrete creator or adapter, and never touches
SQLAlchemy.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.application.readings.dto import ReadingDto
from src.application.readings.service import DeviceNotFoundError, ReadingIngest
from src.application.sensors.service import SensorService
from src.domain.sensors.creators import available_sensor_types
from src.domain.sensors.entity import Sensor
from src.infrastructure.db import get_db
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.reading_repository import ReadingRepository

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


class CreateSensorRequest(BaseModel):
    type: str = Field(description="Creator key: moisture or light.")
    display_name: str | None = Field(default=None, description="Optional label.")


class SensorResponse(BaseModel):
    id: UUID
    device_type: str
    display_name: str
    default_config: dict[str, Any]
    # Phase 5, read from the columns. The copy inside default_config is now
    # only history; the column is what the sampler uses.
    sampling_interval_seconds: int
    tracking_enabled: bool


def get_service(session: Session = Depends(get_db)) -> SensorService:
    """Build the service for one request, wired to that request's session."""
    return SensorService(DeviceRepository(session))


def get_ingest(session: Session = Depends(get_db)) -> ReadingIngest:
    """The one writer of sensor_readings, wired to this request's session."""
    return ReadingIngest(DeviceRepository(session), ReadingRepository(session))


def _to_response(sensor: Sensor) -> SensorResponse:
    return SensorResponse(
        id=sensor.id,
        device_type=sensor.device_type,
        display_name=sensor.display_name,
        default_config=sensor.default_config,
        sampling_interval_seconds=sensor.sampling_interval_seconds,
        tracking_enabled=sensor.tracking_enabled,
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


# -- Phase 5: readings ------------------------------------------------------


@router.post(
    "/{device_id}/read",
    response_model=ReadingDto,
    status_code=status.HTTP_201_CREATED,
    summary="Take a reading now",
    description=(
        "Asks this device's adapter for a value and stores it. A device on the "
        "mqtt protocol cannot be read on demand and returns 400, because it "
        "publishes for itself rather than answering questions."
    ),
)
def take_reading(
    device_id: UUID,
    ingest: ReadingIngest = Depends(get_ingest),
) -> ReadingDto:
    try:
        return ingest.take_reading(device_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        # AdapterError is a ValueError, so this one catch covers every adapter
        # failure without the router importing anything adapter-shaped.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{device_id}/readings",
    response_model=list[ReadingDto],
    summary="Recent readings for a device",
    description="Newest first. A device with no readings returns an empty list.",
)
def list_readings(
    device_id: UUID,
    limit: int = Query(default=20, ge=1, le=200, description="How many rows to return."),
    ingest: ReadingIngest = Depends(get_ingest),
) -> list[ReadingDto]:
    try:
        return ingest.list_readings(device_id, limit)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc