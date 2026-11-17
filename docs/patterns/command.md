# Command — Phase 10

## Why commands

In Phase 9 a command was just a word like `"start_pump"` sent to the actuator.
Nobody checked whether it made sense right now, and only the execution log
remembered it.

Now every command is a small object. It knows which device it is for, what
extra data it carries, what state the device should end up in, and how to send
itself to the actuator. Because all commands look the same from the outside,
one service can check, run and record every one of them in exactly the same way.

The three commands in this phase are `StartPumpCommand`, `StopPumpCommand` and
`SetLightLevelCommand`.

## Who does what

- **The command** knows *what* to do. It has one method: `execute(port)`.
- **The invoker** (`CommandInvoker`) runs any command without knowing which one
  it is holding.
- **The registry** turns a name like `"start_pump"` into the right class.
- **The service** (`CommandService`) decides *whether* to run it, and records
  what happened.
- **The actuator port** from Phase 9 does the actual work, still wrapped in
  logging and max run time.

There is no `if command_type == "start_pump"` anywhere. Adding a new command
means writing one new class and adding one line to the registry.

## What happens when you send one

1. If the device isn't an actuator, you get a 404 and nothing is saved.
2. If the command name is unknown or the payload is wrong, you get a 400 and
   nothing is saved.
3. If the command isn't allowed in the device's current state, it is saved as
   **rejected** and you get a 409. Nothing is sent and the state stays the same.
4. Otherwise it goes through the Phase 9 chain. If max run time blocks it, it
   is saved as **failed**, and the state stays the same.
5. If it went through, the state changes (only if it's actually different) and
   it is saved as **success**.

That's why setting the level on a light that's already on doesn't count as a
state change. It was running before and it's still running.

## Why an object and not a function

A plain function like `start_pump(id)` could do the work. But you can't look a
function up by name, it doesn't carry its own target state or payload rules,
and it can't be saved in the same shape as every other command. An object can
do all of that, so the service never needs a special case.

## Why the router doesn't call the actuator itself

If each route talked to the actuator directly, each one would have to repeat
the state check, the state change and the logging, and sooner or later one of
them would forget a step. With commands there is one path, always in the same
order, always through the decorators.

Phase 9's demo route `POST /api/actuators/{id}/apply` skipped all of that, so
it was removed. `POST /api/commands` is now the only way in.

## The history

Every command that gets past steps 1 and 2 leaves one row in `command_log`, so
you can always see what was asked, not just what worked:

| What happened | status | error_message |
|---|---|---|
| It worked | success | empty |
| Max run time stopped it | failed | Max run time exceeded |
| Not allowed right now | rejected | why, and what is allowed instead |

On the dashboard, the buttons in Controls are greyed out when a command isn't
allowed, and the history table shows every row, newest first.

## Where it is in the code

    domain/commands/                  the command classes, the registry and the invoker
    domain/actuators/state.py         set_light_level added as a setting command
    application/commands/service.py   the five steps above
    infrastructure/persistence/command_log_repository.py
    interfaces/api/commands.py        POST and GET /api/commands
    frontend/src/components/commands/CommandPanel.tsx
    tests/test_commands.py
    tests/test_commands_api.py

## API

- `POST /api/commands` with `{ "command_type": "start_pump", "device_id": "…", "payload": {} }`
- `GET /api/commands?limit=50`, newest first, between 1 and 200 rows

## Next

In Phase 11 (Observer), a successful or failed command will also send out an
event that other parts of the app can listen to.