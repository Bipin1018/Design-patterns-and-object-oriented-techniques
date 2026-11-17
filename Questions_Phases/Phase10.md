# Phase 10 — Command questions

**Pattern / focus:** Command.

**Read first:** [Guide 10](../../materials/guides/10-command.md) · [Requirements](requirements.md)

## How to answer

- Use your own wording. Do not paste teaching-example types (for example editor undo commands) as if they were your greenhouse classes.
- When a question asks about _this application_, refer to command objects, the invoker, `command_log`, and the controls UI from the lab.
- Short answers are fine when the question is narrow. Write a few sentences when it asks you to explain or compare.
- Write each answer inside the matching **Your Answer** note. Replace the placeholder; leave the question text unchanged.

## A. Pattern

1. State the intent of Command in plain language. What does it mean to **objectify a request**, and what can you do with that object that you cannot do with a bare `actuator.start()` call (queue, audit, undo, history)?

> [!NOTE]
> **_Your Answer_**
>
> Command turns a request into an object. Instead of calling `actuator.start()` straight away, you build something like `StartPumpCommand(device_id, payload)` that holds everything about the request: which device, what data, what state it should lead to, and how to carry it out with `execute(port)`.
>
> A bare call happens and is gone. An object can be checked before it runs, passed to whoever should run it, stored in a queue, written to a log, and kept as history. If it remembers enough, it can also be undone later. In our app, the object is what lets us check it against `allowed_commands` first and save every attempt in `command_log`.

2. Name the participants (**command**, **receiver**, **invoker**, **client**). Who creates the command, who triggers `execute()`, and who actually changes actuator/hardware state?

> [!NOTE]
> **_Your Answer_**
>
> The command is `Command` and its subclasses `StartPumpCommand`, `StopPumpCommand` and `SetLightLevelCommand`. The receiver is the decorated `ActuatorPort` from Phase 9, which does the real work. The invoker is `CommandInvoker`. The client is `CommandService`.
>
> `CommandService.submit` creates the command through `command_for`, which looks the name up in `COMMAND_REGISTRY`. `CommandInvoker.run` triggers `execute()`. The actuator itself is driven by the port: the command calls `port.apply(...)`, which goes through logging and max run time to the simulation adapter. The stored state in `actuator_states` is changed afterwards by `ActuatorStateService.transition`, and only if the command went through.

3. If a command supports undo, when must it capture the data needed to reverse the action? Why is "capture **before** mutate" critical?

> [!NOTE]
> **_Your Answer_**
>
> It has to save the old values before it changes anything, in `execute()` and before calling the port. For example, an undoable `SetLightLevelCommand` would first read and keep the light's current level, then set the new one. Undo would then set the old level back.
>
> If you try to save it after the change, the old value is already gone and there is nothing to go back to. Our commands don't support undo yet, but if they did, the previous state from `actuator_states` and the previous level would have to be read first.

## B. This phase of the application

4. Which command types did you implement (for example `start_pump`, `stop_pump`, `set_light_level`)? Why does the HTTP handler create a command and pass it to an **invoker** (or application service) instead of calling the actuator adapter from the router?

> [!NOTE]
> **_Your Answer_**
>
> We implemented `start_pump` (`StartPumpCommand`, leads to `running`), `stop_pump` (`StopPumpCommand`, leads to `idle`) and `set_light_level` (`SetLightLevelCommand`, leads to `running`, with a level from 0 to 100 that defaults to 1).
>
> The router for `POST /api/commands` only passes the request to `CommandService` and turns errors into status codes. If the router called the adapter itself, every route would have to repeat the state check, the state change and the logging, and it would be easy to skip one, or to use the raw adapter and miss the decorators. With the service and the invoker there is one path that every command takes, in the same order. That's also why we removed the Phase 9 demo route `/api/actuators/{id}/apply`.

5. Walk through the execute path: (1) consult State / `allowed_commands`, (2) if illegal → **rejected**, (3) if legal → decorated `apply`, update `actuator_states`, log **success** or **failed**. Why must a rejected command **not** change actuator state and **not** reach inner `apply`?

> [!NOTE]
> **_Your Answer_**
>
> First `CommandService.submit` checks that the device is an actuator and that the command name is known. Then it loads the stored state into an `ActuatorContext` and checks whether the command is in `allowed_commands()`. If it isn't, it writes a `rejected` row to `command_log` and stops, and the API answers 409. If it is allowed, `CommandInvoker` runs it through the decorated port from `port_for`. If max run time blocks it, a `failed` row is written. If it goes through, the state is moved with `ActuatorStateService.transition` (only if the target is different) and a `success` row is written.
>
> A rejected command was never allowed to happen. If it reached `apply`, the pump would actually do something it shouldn't, like starting while it's in maintenance. If it changed the state, the database would say something that isn't true. Rejected means "nothing happened", so the only trace it leaves is the row in `command_log`.

6. Distinguish **`rejected`** vs **`failed`** vs **`success`** in `command_log`. Give one greenhouse example of each. Why is "illegal in this state" not the same as "policy or adapter error after the command was accepted"?

> [!NOTE]
> **_Your Answer_**
>
> `success` means the command was allowed, went through the port, and the state was updated if needed. Example: `start_pump` on an idle pump, which is now `running`.
>
> `rejected` means the command wasn't allowed in the current state, so it was never sent. Example: `stop_pump` on a pump that is already idle. The message says what is allowed instead.
>
> `failed` means the command was allowed, but something on the way said no. Example: `stop_pump` on a pump that has been running for over 30 minutes, which max run time blocks with "Max run time exceeded".
>
> They are different questions. Rejected is about the rules of the lifecycle: this command makes no sense right now. Failed is about what happened when we tried: the command made sense, but a policy or the device refused. Keeping them apart tells the user whether they asked for the wrong thing or whether something blocked a valid request.

7. Why is `command_log` a **different** table from Phase 9 `actuator_execution_log`? What concern does each log record (operator intent vs policy/adapter attempt)?

> [!NOTE]
> **_Your Answer_**
>
> `command_log` records what the user asked for: which command, which device, what payload, and how it ended. That includes rejected commands, which never get near the actuator.
>
> `actuator_execution_log` records what reached the decorated port: whether that attempt worked and which policies took part, like `["maxRunTime", "logging"]`.
>
> They answer different questions. A rejected command only shows up in `command_log`. A failed or successful command shows up in both. Mixing them in one table would blur "what was asked" and "what the device layer did", and the Phase 9 log would suddenly need columns it doesn't care about.

## C. Compare, contrast, and scenarios

8. Contrast Command with **Strategy**. Strategy is an interchangeable **algorithm** (decide / quote). Command is a **side-effectful request** with history. How do they cooperate in this app (Phase 6 recommends; Phase 10 executes)?

> [!NOTE]
> **_Your Answer_**
>
> Strategy decides. In Phase 6 each location picks a strategy, and evaluating it gives a recommendation, like "water this zone", without touching anything. You can swap one strategy for another and get a different answer.
>
> Command does. It changes something real, like starting the pump, and leaves a row in `command_log`.
>
> They fit together as "think, then act". Right now a person reads the recommendation in the dashboard and clicks a button in Controls, which sends a command. Later, a recommendation could be turned into a `StartPumpCommand` automatically, and it would still go through the same checks and logs as a click.

9. Contrast Command with **State**. Who **triggers** the action, and who **decides whether it is legal**? Why must commands not bypass state guards?

> [!NOTE]
> **_Your Answer_**
>
> Command is how an action gets started. The user clicks a button, the API builds the command, and the invoker runs it. State decides whether it is allowed. `ActuatorContext` knows the actuator's current state and gives `allowed_commands()`, and `transition()` refuses any move that isn't in the table.
>
> If a command skipped the state check, you could start a pump that is off or in maintenance, or stop one that isn't running, and `actuator_states` would stop matching reality. The rules from Phase 8 only mean something if every command goes through them. That's why `CommandService` checks `allowed_commands()` first and saves the new state with `ActuatorStateService.transition`, which runs the same guard again.

10. The controls UI should disable actions that are not in `allowed_commands`. Why must the **backend** still reject illegal commands even if the UI is correct? What happens if a classmate's command calls the raw adapter and skips State and Decorator?

> [!NOTE]
> **_Your Answer_**
>
> The UI only knows what it loaded last. Another tab or another user could have changed the state in the meantime, and anyone can send a request straight to `POST /api/commands` from Scalar or curl without using the buttons at all. Disabled buttons are just a convenience. The backend is the one that has to enforce the rules, which is why it still answers 409 and writes a `rejected` row.
>
> If a command called the raw adapter, it would skip everything. There would be no state check, so a pump in maintenance could start. There would be no max run time, so a pump could run forever. Nothing would be written to `actuator_execution_log` or `command_log`. And `actuator_states` would not be updated, so the dashboard would show the pump as idle while it is actually running.