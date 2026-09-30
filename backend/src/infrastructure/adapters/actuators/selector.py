"""Choosing an actuator adapter for a device.

Mirrors the sensor selector, deliberately. Only the simulation family has an
adapter in Phase 5, so anything else is refused rather than silently ignored.
A pump that quietly does nothing is worse than one that says it cannot.

Phase 9 wraps what this returns; Phase 10 calls it.
"""

from src.domain.actuators.ports import ActuatorPort
from src.domain.devices.entity import Device
from src.domain.sensors.errors import AdapterError
from src.infrastructure.adapters.actuators.simulation import SimulationActuatorAdapter
from src.infrastructure.adapters.sensors.selector import PROTOCOL_SIMULATION, protocol_of

# One instance, so its in-memory log survives across calls within a process.
_SIMULATION = SimulationActuatorAdapter()


def get_actuator_port(device: Device) -> ActuatorPort:
    """The adapter that can drive this device."""
    if device.role != "actuator":
        raise AdapterError(f"Device {device.id} is a sensor, not an actuator.")

    protocol = protocol_of(device)
    if protocol == PROTOCOL_SIMULATION:
        return _SIMULATION

    raise AdapterError(
        f"No actuator adapter for protocol '{protocol}'. "
        f"Only '{PROTOCOL_SIMULATION}' is driven in this phase."
    )