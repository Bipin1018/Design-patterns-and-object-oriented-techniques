"""HTTP routes for devices."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.application.devices.dto import ActuatorStateDto, DeviceDto, TransitionRequestDto
from src.application.devices.family_service import DeviceFamilyService
from src.application.devices.mappers import device_to_dto, devices_to_dtos
from src.application.devices.sampling_service import DeviceNotFoundError, SamplingService
from src.application.devices.state_service import ActuatorNotFoundError, ActuatorStateService
from src.application.locations.config_service import LocationNotFoundError
from src.application.locations.zone_assignment_service import ZoneAssignmentService
from src.application.readings.dto import UpdateSamplingRequestDto
from src.domain.actuators.state import ACTUATOR_STATES, IllegalTransitionError, UnknownStateError
from src.domain.devices.family_factory import available_families
from src.domain.devices.sampling import MIN_SAMPLING_INTERVAL_SECONDS
from src.infrastructure.db import get_db
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.location_repository import LocationRepository

router = APIRouter(prefix="/api/devices", tags=["devices"])


def get_service(session: Session = Depends(get_db)) -> DeviceFamilyService:
    return DeviceFamilyService(DeviceRepository(session))


def get_assignment_service(session: Session = Depends(get_db)) -> ZoneAssignmentService:
    return ZoneAssignmentService(LocationRepository(session))


def get_sampling_service(session: Session = Depends(get_db)) -> SamplingService:
    return SamplingService(DeviceRepository(session))


def get_state_service(session: Session = Depends(get_db)) -> ActuatorStateService:
    return ActuatorStateService(ActuatorStateRepository(session))


class AssignZoneRequest(BaseModel):
    """Body of PATCH /api/devices/{id}/zone.

    Only the zone. location_id is copied from the zone by the service, so the
    client cannot send one that disagrees with it.
    """

    zone_id: UUID | None = Field(
        default=None,
        description="Zone to place the device in, or null to clear.",
    )


@router.get("", response_model=list[DeviceDto], summary="List devices")
def list_devices(
    family: str | None = Query(default=None, description="Filter by device family."),
    role: str | None = Query(default=None, description="Filter by role: sensor or actuator."),
    service: DeviceFamilyService = Depends(get_service),
    states: ActuatorStateService = Depends(get_state_service),
) -> list[DeviceDto]:
    return states.attach(devices_to_dtos(service.list_devices(device_family=family, role=role)))


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
    states: ActuatorStateService = Depends(get_state_service),
) -> list[DeviceDto]:
    try:
        devices = service.provision_family(family)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    # New actuators get their idle row here, so every actuator has a stored state.
    return states.initialise(devices_to_dtos(devices))


@router.patch(
    "/{device_id}/zone",
    response_model=DeviceDto,
    summary="Place a device in a zone, or clear its placement",
)
def assign_zone(
    device_id: UUID,
    payload: AssignZoneRequest,
    service: ZoneAssignmentService = Depends(get_assignment_service),
    states: ActuatorStateService = Depends(get_state_service),
) -> DeviceDto:
    try:
        return states.attach_one(device_to_dto(service.assign(device_id, payload.zone_id)))
    except LocationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# -- Phase 5: sampling ------------------------------------------------------


@router.patch(
    "/{device_id}/sampling",
    response_model=DeviceDto,
    summary="Change how often a device is sampled",
    description=(
        f"Minimum interval is {MIN_SAMPLING_INTERVAL_SECONDS} seconds. Setting "
        "tracking_enabled to false stops the sampler for this device; a manual "
        "read still works."
    ),
)
def update_sampling(
    device_id: UUID,
    payload: UpdateSamplingRequestDto,
    service: SamplingService = Depends(get_sampling_service),
    states: ActuatorStateService = Depends(get_state_service),
) -> DeviceDto:
    try:
        return states.attach_one(service.update_sampling(device_id, payload))
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# -- Phase 8: actuator state ------------------------------------------------


@router.get(
    "/{device_id}/state",
    response_model=ActuatorStateDto,
    summary="Current lifecycle state of an actuator",
    responses={404: {"description": "No actuator with that id (sensors count as missing)."}},
)
def get_state(
    device_id: UUID,
    states: ActuatorStateService = Depends(get_state_service),
) -> ActuatorStateDto:
    try:
        return states.get_state(device_id)
    except ActuatorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{device_id}/transition",
    response_model=ActuatorStateDto,
    summary="Move an actuator to another state (demo)",
    description=(
        f"States: {', '.join(ACTUATOR_STATES)}. The domain's transition table decides "
        "which moves are legal; an illegal one returns 409 and the stored state does "
        "not change. This endpoint is for demos and tests. From Phase 10, actions go "
        "through Command."
    ),
    responses={
        400: {"description": "Unknown target state."},
        404: {"description": "No actuator with that id (sensors count as missing)."},
        409: {"description": "Illegal transition. The stored state is unchanged."},
    },
)
def transition_actuator(
    device_id: UUID,
    payload: TransitionRequestDto,
    states: ActuatorStateService = Depends(get_state_service),
) -> ActuatorStateDto:
    try:
        return states.transition(device_id, payload.target)
    except ActuatorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UnknownStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc