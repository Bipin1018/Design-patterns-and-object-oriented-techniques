"""The sensor port.

SensorPort is a promise, not an implementation: hand it a Device and it hands
back a Reading. It does not say whether the value was generated in software,
translated from a vendor payload, or parsed from a message.

The application layer depends on this class. Only the selector in the
infrastructure layer knows which concrete adapter answers for a given device,
which is what lets a new protocol arrive without touching a use case.
"""

from abc import ABC, abstractmethod

from src.domain.devices.entity import Device
from src.domain.sensors.reading import Reading


class SensorPort(ABC):
    @abstractmethod
    def read(self, device: Device) -> Reading:
        """Take one reading from this device, normalized.

        Raises AdapterError if this adapter cannot serve the device.
        """
    