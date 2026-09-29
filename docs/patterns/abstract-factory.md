# Abstract Factory

## Problem

The greenhouse runs one of two ways: on fake devices for development, or on
real hardware. Either way you need the same four things, and they all have to
match. A fake pump cannot be plugged into a real pin.

If you add devices one at a time, it is easy to end up with a half fake, half
real set that does not work.

## Solution

Ask for a whole kit instead of one device.

`DeviceFamilyFactory` says that a kit gets made. Each factory below it decides
what goes in that kit and what settings the parts use.

```text
DeviceFamilyFactory (abstract)
├── SimulationDeviceFactory -> 2 sensors + 2 actuators, protocol "sim"
└── EdgeHardwareFactory     -> 2 sensors + 2 actuators, protocol "gpio-stub"
```

`get_family_factory("simulation")` gives you the right one. An unknown name
raises an error, the API turns it into a 400, and nothing gets saved.

## How it differs from Factory Method

Factory Method asks: which one do I make?

Abstract Factory asks: which matching set do I make?

They work together. The family factories call the Phase 2 creators to build
their sensors, then add the family and its protocol. The creators still decide
what a moisture sensor is.

## Why Device is not the same as the DTO

`Device` is what a device means to the greenhouse. `DeviceDto` is what the JSON
looks like. Keeping them apart means the JSON can change without touching the
rules, and the rules stay free of web code. The mapper is the only thing that
knows both.

## Where to look

| File | Role |
|------|------|
| `backend/src/domain/devices/entity.py` | the `Device` entity |
| `backend/src/domain/devices/family_factory.py` | the factories and the registry |
| `backend/src/application/devices/dto.py` | `DeviceDto`, the JSON shape |
| `backend/src/application/devices/mappers.py` | device to DTO |
| `backend/src/application/devices/family_service.py` | factory, then save |
| `backend/src/infrastructure/persistence/device_repository.py` | rows, and the filters |
| `backend/src/interfaces/api/devices.py` | routes; turns the error into 400 |
| `backend/tests/test_family_factory.py` | four devices; families differ |

## Exercise: add a third family

1. Add a `LabBenchFactory` in `family_factory.py` with its own labels and
   protocol, making the same four device types.
2. Add `"lab": LabBenchFactory()` to `_FAMILIES`.
3. Add a test next to the others.
4. On the frontend, add the name to `DeviceFamily` and to the switcher.

Nothing else changes. The service, repository, router and mappers keep working,
because none of them knows the factories by name.
