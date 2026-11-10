# Decorator — Phase 9

## Why decorators

Before a command reaches an actuator, some rules should run around it: write
a log row, and refuse if the actuator has been running too long.

Instead of putting those checks in the router or inside the adapter, each rule
is its own small class that wraps the actuator port. Every wrapper has the same
`apply` method as the thing it wraps, so the caller never knows how many
wrappers there are.

## The chain

    LoggingActuatorDecorator
      → MaxRunTimeActuatorDecorator
        → SimulationActuatorAdapter

The chain is built in one place, `ActuatorExecutionService.port_for`.

Logging is outermost because max run time refuses by raising an error. Only a
layer outside it can still write the row for a blocked command.

## What gets logged

Every attempt writes one row to `actuator_execution_log`:

| Case | success | policy_applied | message |
|---|---|---|---|
| Went through | true | `["logging"]` | null |
| Blocked | false | `["maxRunTime", "logging"]` | Max run time exceeded |

Max run time blocks when the actuator is `running` and `updated_at` is at
least 30 minutes old. When it blocks, the adapter is never called.

The command name is not checked yet, so any command succeeds unless it is
blocked. Phase 10 checks `allowed_commands`.

## Decorator vs inheritance

With inheritance, every mix of rules needs its own subclass, such as
`LoggingMaxRunTimeSimulationAdapter`, and the number of classes grows with
each new rule.

With decorators, each rule is one class, and they are combined when the chain
is built. A new rule means one new wrapper. The adapter itself never changes.

## Where it is in the code

    domain/actuators/ports.py                                    ActuatorPort, ExecutionLogPort
    domain/actuators/policies.py                                 policy names, 30-minute rule
    infrastructure/adapters/actuators/logging_decorator.py
    infrastructure/adapters/actuators/max_runtime_decorator.py
    infrastructure/persistence/execution_log_repository.py
    application/actuators/execution_service.py                   builds the chain
    interfaces/api/actuators.py
    frontend/src/components/actuators/ExecutionLog.tsx
    tests/test_actuator_decorators.py
    tests/test_actuator_executions_api.py

## API

- `GET /api/actuators/executions?limit=20` — newest rows first
- `POST /api/actuators/{id}/apply` with `{ "command": "start_pump" }` — demo
  endpoint: 404 missing actuator, 409 blocked (the row is still written)

## Next phases

Phase 10 (Command) will send commands through this same decorated port and
add `command_log`.