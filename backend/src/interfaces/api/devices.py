"""HTTP routes for devices."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.application.devices.dto import DeviceDto
from src.application.devices.family_service import DeviceFamilyService
from src.application.devices.mappers import device_to_dto, devices_to_dtos
from src.application.locations.config_service import LocationNotFoundError
from src.application.locations.zone_assignment_service import ZoneAssignmentService
from src.domain.devices.family_factory import available_families
from src.infrastructure.db import get_db
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.location_repository import LocationRepository

router = APIRouter(prefix="/api/devices", tags=["devices"])


def get_service(session: Session = Depends(get_db)) -> DeviceFamilyService:
    return DeviceFamilyService(DeviceRepository(session))


def get_assignment_service(session: Session = Depends(get_db)) -> ZoneAssignmentService:
    return ZoneAssignmentService(LocationRepository(session))


class AssignZoneRequest(BaseModel):
    """Body of PATCH /api/devices/{id}/zone.

    Only the zone. location_id is copied from the zone by the service, so the
    client cannot send one that disagrees with it.
    """

    zone_id: UUID | None = Field(default=None, description="Zone to place the device in, or null to clear.")


@router.get("", response_model=list[DeviceDto], summary="List devices")
def list_devices(
    family: str | None = Query(default=None, description="Filter by device family."),
    role: str | None = Query(default=None, description="Filter by role: sensor or actuator."),
    service: DeviceFamilyService = Depends(get_service),
) -> list[DeviceDto]:
    return devices_to_dtos(service.list_devices(device_family=family, role=role))


@router.post(
    "/provision",
    response_model=list[DeviceDto],
    status_code=status.HTTP_201_CREATED,
    summary="Provision a device family",
    description=f"Creates a matching kit. Valid families: {', '.join(available_families())}.",
)
def provision_family(
    family: str = Query(description="Family key to provision."),
    service: DeviceFamilyService = Depends(get_service),
) -> list[DeviceDto]:
    try:
        devices = service.provision_family(family)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return devices_to_dtos(devices)


@router.patch(
    "/{device_id}/zone",
    response_model=DeviceDto,
    summary="Place a device in a zone, or clear its placement",
)
def assign_zone(
    device_id: UUID,
    payload: AssignZoneRequest,
    service: ZoneAssignmentService = Depends(get_assignment_service),
) -> DeviceDto:
    try:
        return device_to_dto(service.assign(device_id, payload.zone_id))
    except LocationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc