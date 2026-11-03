# State — Phase 8

## Why a state machine

An actuator can only do certain things depending on what it is doing now. A
running pump cannot be started again, and a faulted one must be reset first.

Instead of writing `if state == "idle"` checks in routers or React, the rules
live in one place in the domain. `ActuatorContext` holds the current state and
checks every move against one transition table.

## States

- **off** — powered down
- **idle** — ready, doing nothing (the starting state)
- **running** — pumping or lit
- **error** — faulted, waiting for a reset
- **maintenance** — taken out of service

## Legal transitions

| From | To |
|---|---|
| off | idle, error |
| idle | running, off, maintenance, error |
| running | idle, error |
| error | idle, maintenance |
| maintenance | idle, off, error |

Anything else is illegal, including staying in the same state. For example,
running → maintenance is rejected: the pump must stop first.

An illegal move raises `IllegalTransitionError`. The API returns 409 and the
stored state does not change.

## Allowed commands

`allowed_commands` is worked out from the current state:

| Transition | Pump | Light |
|---|---|---|
| idle → running | start_pump | turn_on_light |
| running → idle | stop_pump | turn_off_light |
| off → idle | power_on | power_on |
| idle / maintenance → off | power_off | power_off |
| idle / error → maintenance | start_maintenance | start_maintenance |
| maintenance → idle | finish_maintenance | finish_maintenance |
| error → idle | reset | reset |

Moving to error has no command, because a fault comes from the device, not
from a user. The demo endpoint can still set it for testing.

## Where it is in the code

Domain:

    domain/actuators/state.py      states, transition table, command names
    domain/actuators/context.py    ActuatorContext

Application:

    application/devices/dto.py             state and allowed_commands on DeviceDto
    application/devices/state_service.py   load, transition, save

Infrastructure:

    persistence/models.py                      ActuatorStateRow
    persistence/actuator_state_repository.py   reads and writes actuator_states

API:

    interfaces/api/devices.py   state on device responses, GET state, POST transition

Frontend:

    components/devices/ActuatorStateBadge.tsx   badge, tooltip, demo move

Tests:

    tests/test_actuator_state.py
    tests/test_actuator_state_api.py

## Database

`actuator_states` has one row per actuator: `device_id`, `state` and
`updated_at`. State is stored in the database, not in the FastAPI process, so
it survives a restart.

Existing actuators were seeded as `idle` in the migration. New actuators get
an `idle` row when they are provisioned.

## API

- `GET /api/devices` — each device includes `state` and `allowed_commands`
  (sensors get `null` and `[]`)
- `GET /api/devices/{id}/state` — one actuator's state
- `POST /api/devices/{id}/transition` with `{ "target": "running" }` — demo
  endpoint: 404 missing actuator, 409 illegal move, 400 unknown state

## Next phases

Phase 10 (Command) will use `target_for(command)` and the same `transition`
check, so a command cannot skip the rules.