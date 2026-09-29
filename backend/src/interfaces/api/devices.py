"""HTTP routes for devices.

Thin on purpose: read the query, call the service, map to DTOs. It never names
a concrete factory and never touches SQLAlchemy.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.devices.dto import DeviceDto
from src.application.devices.family_service import DeviceFamilyService
from src.application.devices.mappers import devices_to_dtos
from src.domain.devices.family_factory import available_families
from src.infrastructure.db import get_db
from src.infrastructure.persistence.device_repository import DeviceRepository

router = APIRouter(prefix="/api/devices", tags=["devices"])


def get_service(session: Session = Depends(get_db)) -> DeviceFamilyService:
    """Build the service for one request, wired to that request's session."""
    return DeviceFamilyService(DeviceRepository(session))


@router.get("", response_model=list[DeviceDto], summary="List devices")
def list_devices(
    family: str | None = Query(default=None, description="Filter by device family."),
    role: str | None = Query(default=None, description="Filter by role: sensor or actuator."),
    service: DeviceFamilyService = Depends(get_service),
) -> list[DeviceDto]:
    devices = service.list_devices(device_family=family, role=role)
    return devices_to_dtos(devices)


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
        # The registry rejected the family, so nothing was written.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return devices_to_dtos(devices)