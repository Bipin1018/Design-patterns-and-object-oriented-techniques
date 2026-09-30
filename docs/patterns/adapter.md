# Adapter

## Problem

The greenhouse reads sensors. No two sensors speak the same language.

A simulated sensor has no protocol at all. A supplier reports moisture as a
whole number out of a thousand, so 412 means 0.412, with a timestamp counted in
milliseconds. An ESP32 sends a small message over MQTT whenever it likes, and
cannot be asked for a value at all.

Without a pattern, everything that wants a reading has to know all three
formats. Add a fourth supplier and you edit all of them.

## Solution

Put a port in between. The port is a promise: give me a device, I give you a
reading. It says nothing about where the value came from.

    SensorPort (abstract)
    ├── SimulationSensorAdapter -> invents a value, source "simulation"
    ├── VendorStubSensorAdapter -> converts their units and timestamp
    └── MqttSensorAdapter       -> reads an incoming message

All three produce the same `Reading`: device_id, value, unit, source,
recorded_at. Everything above the adapters sees only that.

`get_sensor_port(device)` picks the right one. An MQTT device raises an error
and the API turns it into a 400, because that device reports for itself and
making up a value would be inventing data it never sent.

Adapters translate. They do not decide. The vendor adapter turns 412 into
0.412. Whether 0.412 is dry enough to water is a separate question, and it
belongs somewhere else.

## Where to look

| File | Role |
|------|------|
| `backend/src/domain/sensors/reading.py` | the `Reading` value object |
| `backend/src/domain/sensors/ports.py` | `SensorPort` |
| `backend/src/domain/actuators/ports.py` | `ActuatorPort` |
| `backend/src/domain/sensors/errors.py` | `AdapterError`, a ValueError so 400 catches it |
| `backend/src/domain/devices/sampling.py` | the 5 second floor |
| `backend/src/infrastructure/adapters/sensors/simulation.py` | generates a value |
| `backend/src/infrastructure/adapters/sensors/vendor_stub.py` | converts their payload |
| `backend/src/infrastructure/adapters/sensors/mqtt.py` | converts a message |
| `backend/src/infrastructure/adapters/sensors/selector.py` | picks one; the only file naming adapters |
| `backend/src/infrastructure/adapters/actuators/simulation.py` | records a command, drives nothing |
| `backend/src/infrastructure/persistence/reading_repository.py` | rows in `sensor_readings` |
| `backend/src/application/readings/service.py` | `ReadingIngest`, the only writer |
| `backend/src/application/readings/sampler.py` | `run_once(now)` |
| `backend/src/interfaces/api/sensors.py` | read and history routes |
| `backend/tests/test_adapters.py` | translation; no database, no broker |
| `backend/tests/test_readings_api.py` | endpoints and the sampler clock |

## Exercise: add a third vendor

Say a supplier arrives sending XML.

1. Add `AcmeSensorAdapter(SensorPort)` in `adapters/sensors/acme.py`. Read
   their XML, return a `Reading` with `source="acme"`.
2. Add one line to the selector so it picks that adapter.
3. Add a test that hands it a fixed XML string.

Nothing else changes. The ingest service, the sampler, the repository, the
router and the database all keep working, because none of them knows the
adapters by name.