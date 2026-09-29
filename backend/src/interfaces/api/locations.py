"""HTTP routes for locations, zones and the devices placed in them.

Thin: read the request, call a service, map the result. Domain errors become
status codes here, because the domain knows nothing about HTTP.

None of these handlers calls LocationConfigBuilder. Only the create route
reaches it, and only through LocationConfigService.build_and_save.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.application.devices.dto import DeviceDto
from src.application.devices.mappers import devices_to_dtos
from src.application.locations.config_service import (
    LocationConfigService,
    LocationNotFoundError,
)
from src.application.locations.dto import (
    BuildLocationConfigRequestDto,
    LocationConfigDto,
    LocationSummaryDto,
    ZoneDto,
    ZoneInputDto,
)
from src.application.locations.zone_assignment_service import ZoneAssignmentService
from src.domain.locations.errors import ConfigurationError
from src.infrastructure.db import get_db
from src.infrastructure.persistence.location_repository import LocationRepository

router = APIRouter(prefix="/api/locations", tags=["locations"])


def get_config_service(session: Session = Depends(get_db)) -> LocationConfigService:
    return LocationConfigService(LocationRepository(session))


def get_assignment_service(session: Session = Depends(get_db)) -> ZoneAssignmentService:
    return ZoneAssignmentService(LocationRepository(session))


def _bad_request(exc: ConfigurationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _not_found(exc: LocationNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# -- Step 6: create and read a config ---------------------------------------


@router.post(
    "/config",
    response_model=LocationConfigDto,
    status_code=status.HTTP_201_CREATED,
    summary="Create a location configuration",
    description="Runs the builder. Nothing is written if validation fails.",
)
def create_config(
    payload: BuildLocationConfigRequestDto,
    service: LocationConfigService = Depends(get_config_service),
) -> LocationConfigDto:
    try:
        return service.build_and_save(payload)
    except ConfigurationError as exc:
        raise _bad_request(exc) from exc


@router.get(
    "/{location_id}/config",
    response_model=LocationConfigDto,
    summary="Read one location configuration",
)
def read_config(
    location_id: UUID,
    service: LocationConfigService = Depends(get_config_service),
) -> LocationConfigDto:
    try:
        return service.get_config(location_id)
    except LocationNotFoundError as exc:
        raise _not_found(exc) from exc


# -- Step 6a: list and delete locations -------------------------------------


@router.get(
    "",
    response_model=list[LocationSummaryDto],
    summary="List locations",
    description="Newest first. An empty database returns an empty list.",
)
def list_locations(
    service: LocationConfigService = Depends(get_config_service),
) -> list[LocationSummaryDto]:
    return service.list_locations()


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a location",
    description="Removes its zones too. Devices survive, unplaced.",
)
def delete_location(
    location_id: UUID,
    service: LocationConfigService = Depends(get_config_service),
) -> Response:
    try:
        service.delete_location(location_id)
    except LocationNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- Step 6c: zones on a saved location -------------------------------------


@router.post(
    "/{location_id}/zones",
    response_model=ZoneDto,
    status_code=status.HTTP_201_CREATED,
    summary="Add a zone to a saved location",
)
def add_zone(
    location_id: UUID,
    payload: ZoneInputDto,
    service: LocationConfigService = Depends(get_config_service),
) -> ZoneDto:
    try:
        return service.add_zone(location_id, payload)
    except LocationNotFoundError as exc:
        raise _not_found(exc) from exc
    except ConfigurationError as exc:
        raise _bad_request(exc) from exc


@router.patch(
    "/{location_id}/zones/{zone_id}",
    response_model=ZoneDto,
    summary="Update a zone",
)
def update_zone(
    location_id: UUID,
    zone_id: UUID,
    payload: ZoneInputDto,
    service: LocationConfigService = Depends(get_config_service),
) -> ZoneDto:
    try:
        return service.update_zone(location_id, zone_id, payload)
    except LocationNotFoundError as exc:
        raise _not_found(exc) from exc
    except ConfigurationError as exc:
        raise _bad_request(exc) from exc


@router.delete(
    "/{location_id}/zones/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a zone",
    description="Rejected with 400 if it is the last zone on the location.",
)
def delete_zone(
    location_id: UUID,
    zone_id: UUID,
    service: LocationConfigService = Depends(get_config_service),
) -> Response:
    try:
        service.delete_zone(location_id, zone_id)
    except LocationNotFoundError as exc:
        raise _not_found(exc) from exc
    except ConfigurationError as exc:
        raise _bad_request(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- Step 6b: the devices in a zone -----------------------------------------


@router.get(
    "/{location_id}/zones/{zone_id}/devices",
    response_model=list[DeviceDto],
    summary="List the devices placed in a zone",
)
def list_zone_devices(
    location_id: UUID,
    zone_id: UUID,
    service: ZoneAssignmentService = Depends(get_assignment_service),
) -> list[DeviceDto]:
    try:
        return devices_to_dtos(service.list_devices(location_id, zone_id))
    except LocationNotFoundError as exc:
        raise _not_found(exc) from exc