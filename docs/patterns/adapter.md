# Adapter

## Problem

The greenhouse reads sensors. No two sensors speak the same language.

A simulated sensor has no protocol at all. A supplier sends
`{"measurement": {"raw": 412, "scale": "permille"}, "capturedAtEpochMs": ...}`.
An ESP32 publishes `{"value": 0.41, "unit": "vwc"}` over MQTT when it feels
like it, and cannot be asked for a value at all.

Without a pattern, everything that wants a moisture reading has to know all
three. Add a fourth supplier and you edit all of them.

## Solution

Put a port in between. The port is a promise: give me a device, I give you a
reading. It says nothing about where the value came from.

```text
SensorPort (abstract)
├── SimulationSensorAdapter -> invents a value, source "simulation"
├── VendorStubSensorAdapter -> translates permille and epoch ms, source "vendor"
└── MqttSensorAdapter       -> translates a dict, source "mqtt"
```

All three produce the same `Reading`: device_id, value, unit, source,
recorded_at. Everything above the adapters sees only that.

`get_sensor_port(device)` picks the right one. An MQTT device raises an error,
the API turns it into a 400, and nothing gets invented.

## Adapters translate, they do not decide

The vendor adapter turns 412 permille into 0.412 vwc. It never decides whether
0.412 is dry enough to water. That is Phase 6's question.

Policy in an adapter means every new supplier has to reimplement it, and two
suppliers could disagree about when to irrigate.

## Why MqttSensorAdapter is not a SensorPort

`SensorPort` promises "ask and receive". An MQTT device cannot be asked. It
publishes when it wants to, and the backend takes what arrives.

So that class offers `translate()` and nothing else. Asking an MQTT device for
a reading is refused with a reason rather than answered with a made-up number.

## How the selector chooses

1. `default_config.vendor_stub` is true → vendor stub
2. `default_config.protocol` is `simulation` → simulation adapter
3. `default_config.protocol` is `mqtt` → no adapter, 400

The vendor stub gets its own key because "vendor" is not a protocol, it is a
supplier. A device could be both vendor-made and MQTT-connected, so keeping
them apart means they cannot collide.

## One ingest path

```text
POST /read                   -> take_reading -> pick adapter, ask it
SimulationSampler.run_once   -> take_reading -> same
Phase 12 MQTT or device HTTP -> record       -> already translated
```

They all go through `ReadingIngest`. Phase 11 publishes `reading.created` from
there, and it can only promise "every reading raises an event" because every
reading passes through one place.

`take_reading` ignores `tracking_enabled`. Tracking off means stop sampling
this device, not stop me reading it myself.

## Why the sampler takes the clock as an argument

`run_once(now)` does not call the clock itself. A test hands it a time ninety
seconds ahead and checks a row appeared, without sleeping for ninety seconds.
The lifespan task passes the real clock.

A device is due when it has no reading, or its last one is older than its
interval. So one you read manually a second ago is not due, and the sampler
does not double up on a button press.

## What changed from Phase 3

Phase 3 wrote `protocol: sim` and `protocol: gpio-stub` as hints. Phase 5 made
them the keys the selector matches on, so they became `simulation` and `mqtt`.
Revision 8017ea920d68 rewrote the old rows and gave the Phase 2 sensors a
protocol, which they never had.

The pin settings stayed on the edge kit. A real ESP32 is wired to GPIO 4 and
reports over MQTT. The pin is its wiring, the protocol is how it talks to us.

That revision also promoted `sampling_interval_seconds` from `default_config`
to a real column and added `tracking_enabled`. The columns are the truth now.
The creators still write the interval into the JSON, but nothing reads it there.

## Where to look

| File | Role |
|------|------|
| `backend/src/domain/sensors/reading.py` | the `Reading` value object |
| `backend/src/domain/sensors/ports.py` | `SensorPort` |
| `backend/src/domain/actuators/ports.py` | `ActuatorPort`, for Phase 9 |
| `backend/src/domain/sensors/errors.py` | `AdapterError`, a ValueError so 400 catches it |
| `backend/src/domain/devices/sampling.py` | the 5 second floor |
| `backend/src/infrastructure/adapters/sensors/simulation.py` | generates from device_type |
| `backend/src/infrastructure/adapters/sensors/vendor_stub.py` | translates their payload |
| `backend/src/infrastructure/adapters/sensors/mqtt.py` | translates a dict |
| `backend/src/infrastructure/adapters/sensors/selector.py` | picks one; the only file naming adapters |
| `backend/src/infrastructure/adapters/actuators/simulation.py` | records the command, drives nothing |
| `backend/src/infrastructure/persistence/reading_repository.py` | rows in `sensor_readings` |
| `backend/src/application/readings/service.py` | `ReadingIngest`, the only writer |
| `backend/src/application/readings/sampler.py` | `run_once(now)` |
| `backend/src/interfaces/api/sensors.py` | read and history routes |
| `backend/tests/test_adapters.py` | translation; no database, no broker |
| `backend/tests/test_readings_api.py` | endpoints and the sampler clock |

## Exercise: add a third vendor

Say a supplier arrives sending XML over serial.

1. Add `AcmeSensorAdapter(SensorPort)` in `adapters/sensors/acme.py`. Parse
   their XML, return a `Reading` with `source="acme"`.
2. Add one line to the selector mapping their flag to it.
3. Add a test that hands `translate` a fixed XML string.

Nothing else changes. `ReadingIngest`, the sampler, the repository, the router,
the database and Phase 6's Strategy all keep working, because none of them
knows the adapters by name.

The same three steps add GPIO, Modbus or DMX. `ActuatorPort` works the same
way, which is why `SimulationActuatorAdapter` exists now even though nothing
drives it — Phase 9 wraps that port, and it has to be there to be wrapped.