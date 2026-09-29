"""Domain Device -> DeviceDto.

The mapping lives here, not on the entity and not in the router. The domain
stays free of Pydantic, and the router stays thin.
"""

from src.application.devices.dto import DeviceDto
from src.domain.devices.entity import Device


def device_to_dto(device: Device) -> DeviceDto:
    """Convert one saved device. Unsaved devices have no id and are rejected."""
    if device.id is None:
        raise ValueError("Cannot map an unsaved device to a DTO: id is None")

    return DeviceDto(
        id=device.id,
        device_type=device.device_type,
        role=device.role,
        device_family=device.device_family,
        display_name=device.display_name,
        default_config=device.default_config,
        zone_id=device.zone_id,
        location_id=device.location_id,
    )


def devices_to_dtos(devices: list[Device]) -> list[DeviceDto]:
    return [device_to_dto(device) for device in devices]