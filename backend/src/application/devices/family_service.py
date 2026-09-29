"""Use cases for device families."""

from src.domain.devices.entity import Device
from src.domain.devices.family_factory import get_family_factory
from src.infrastructure.persistence.device_repository import DeviceRepository


class DeviceFamilyService:
    def __init__(self, repository: DeviceRepository) -> None:
        self._repository = repository

    def provision_family(self, family: str) -> list[Device]:
        """Ask the family factory for a kit, then save the whole set.

        get_family_factory raises ValueError on an unknown family, so a bad
        request never reaches the database.
        """
        factory = get_family_factory(family)
        return self._repository.save_devices(factory.create_device_set())

    def list_devices(
        self,
        *,
        device_family: str | None = None,
        role: str | None = None,
    ) -> list[Device]:
        return self._repository.list_devices(device_family=device_family, role=role)