# Phase 8 — State questions

**Pattern / focus:** State.

**Read first:** [Guide 08](../../materials/guides/08-state.md) · [Requirements](requirements.md)

## How to answer

- Use your own wording. Do not paste teaching-example types (for example support-ticket states) as if they were your greenhouse classes.
- When a question asks about *this application*, refer to actuator lifecycle, persisted state, and `allowed_commands` from the lab.
- Short answers are fine when the question is narrow. Write a few sentences when it asks you to explain or compare.
- Write each answer inside the matching **Your Answer** note. Replace the placeholder; leave the question text unchanged.

## A. Pattern

1. State the intent of the State pattern in plain language. What problem appears when lifecycle is modelled as boolean flags and scattered `if` guards?

> [!NOTE]
> ***Your Answer***
>
> State lets an object behave differently depending on what it is doing right now, and keeps the rules about what can happen next in one place.
>
> With boolean flags, the lifecycle is spread across `is_running`, `is_fault` and similar fields, and every place that acts on the device needs its own `if` checks. Those checks get copied into routers, the UI and services, and the copies drift apart. One place forgets to check for a fault, another lets a running pump start again. Nothing stops two flags being true at once either.

2. Name the participants (**context**, **state interface**, **concrete states**, **client**). How does a successful command lead to a **transition**, and where do **guards** live?

> [!NOTE]
> ***Your Answer***
>
> The context is the object that holds the current state and receives requests. In our app it is `ActuatorContext`. The state interface and concrete states describe what each state allows. We used a transition table for this: each state in `TRANSITIONS` lists the states it may move to, and each legal move has a command name. The client is the code that asks for a change, which is `ActuatorStateService`, called by the device router.
>
> A request names a target. The context checks the table, and if the move is legal it changes its state, and the service then saves it. If the move is not in the table, the context raises and nothing changes. The guards live in the domain, in the context and its table, not in the router or React.

3. What is `allowed_commands` (or equivalent) for? Why is exposing “what can I do **now**?” better than letting the UI guess from a raw state string?

> [!NOTE]
> ***Your Answer***
>
> `allowed_commands` tells the caller what it may do right now, for example `start_pump` when the pump is idle and only `stop_pump` when it is running.
>
> If the UI only got the raw state string, it would have to know the rules itself to decide which buttons to show. That copies the transition table into React, and the two versions drift apart as soon as one changes. When the backend sends the list, the rules stay in one place and the UI only displays what it is given.

## B. This phase of the application

4. Which actuator states did you implement (for example idle, running, error)? Sketch the **legal** transitions (which command or event moves idle → running, running → idle, into error, and out of error).

> [!NOTE]
> ***Your Answer***
>
> We implemented all five states: off, idle, running, error and maintenance. Idle is the starting state.
>
> - idle → running: `start_pump` (or `turn_on_light` for a light)
> - running → idle: `stop_pump` (or `turn_off_light`)
> - off → idle: `power_on`; idle or maintenance → off: `power_off`
> - idle or error → maintenance: `start_maintenance`; maintenance → idle: `finish_maintenance`
> - any state except error → error: a fault reported by the device, so there is no user command for it
> - error → idle: `reset`
>
> Everything else is illegal, for example running → maintenance, because the pump must stop first.

5. Why is actuator state stored in `actuator_states` (or equivalent) rather than only in process memory? What must still be true after you restart the backend?

> [!NOTE]
> ***Your Answer***
>
> Process memory disappears when the backend restarts, and it is not shared if more than one process runs. A pump that was running would suddenly show as idle, and the dashboard would offer the wrong commands.
>
> After a restart, every actuator must still have the same state it had before, and `allowed_commands` must still match it. The `actuator_states` table makes that true, and the restart check in the lab confirms it.

6. An **illegal** transition must raise a domain error and **must not** update the database. Why? Which HTTP status is reasonable for that case (400 or 409), and why should the rule live in the domain rather than in React?

> [!NOTE]
> ***Your Answer***
>
> If an illegal move were saved, the database would hold a state the rules say cannot happen, and every later decision would be based on it. So the context checks first and raises `IllegalTransitionError`, and the service only saves after the check passes. The test confirms that both `state` and `updated_at` are unchanged after a rejected move.
>
> We return 409 Conflict. The request is well formed and the target is a real state, but it conflicts with the actuator's current state. 400 is for a request that is wrong on its own, like an unknown state name such as "flying", and we use 400 for that.
>
> The rule belongs in the domain because React is only one caller. The API, tests and the Phase 10 commands all go through the same check. A rule that lives only in the browser can be skipped by anyone calling the API directly.

7. Device JSON gains `state` and `allowed_commands`. How does the dashboard use those fields (badges, disable illegal buttons)? How does this prepare **Phase 10 Command**?

> [!NOTE]
> ***Your Answer***
>
> The dashboard shows a coloured badge for `state` on each actuator card: slate for idle, emerald for running, red for error and amber for maintenance. Hovering the badge shows the allowed commands, and a line under it lists them. We did not build control buttons yet. The demo picker sends any target, and an illegal one shows the backend's 409 message under the badge. React never decides what is legal.
>
> In Phase 10, the command buttons can be built straight from `allowed_commands`, so only legal actions appear. A command will use `target_for` to find its target state and then go through the same `transition` check, so it cannot skip the rules.

## C. Compare, contrast, and scenarios

8. Contrast State with **Strategy**. Both look like “context delegates to an object.” Who typically **changes** the active object, and is the variation a **lifecycle** or a **selectable policy**? Give a greenhouse example of each (this phase vs Phase 6).

> [!NOTE]
> ***Your Answer***
>
> In State, the object changes itself as part of its lifecycle. A pump moves from idle to running because it was started, and the current state decides what can happen next. In Strategy, someone outside picks the algorithm, and it stays until someone picks another one.
>
> Our actuator lifecycle in this phase is State: the pump moves through idle, running and error as things happen to it. Phase 6 was Strategy: the user saves conservative or aggressive for a location, and that policy stays the same no matter what the sensors say.

9. Contrast State with a pile of booleans (`is_running`, `is_fault`, `is_maintenance`). Why do illegal combinations of flags appear, and how do explicit state objects (or a transition table) prevent that?

> [!NOTE]
> ***Your Answer***
>
> Three booleans allow eight combinations, but only a few make sense. Nothing stops `is_running` and `is_maintenance` both being true, or a fault being set while the pump still counts as running. Every piece of code then has to check for combinations that should never exist.
>
> With one `state` field and a transition table, the actuator is always in exactly one of five states. The table lists every legal move, so an impossible combination cannot be stored, and an illegal move is rejected before it is saved.

10. A classmate puts HTTP status mapping or SQLAlchemy commits **inside** a concrete state class. Another state mutates a flag directly and skips `transition` / `set_state`. Explain why each is a trap.

> [!NOTE]
> ***Your Answer***
>
> HTTP status codes and SQLAlchemy commits do not belong in a state class. The state should only answer what is allowed and where it leads. If it knows about HTTP, it cannot be used outside a web request, and if it commits to the database, its tests need a database. We keep these apart: the domain raises `IllegalTransitionError`, the service saves, and the router turns the error into 409.
>
> A state that changes a flag directly skips the guard. The move is never checked against the table, so an illegal state can be saved, and nothing else in the app knows a change happened. Every change has to go through `transition` so there is only one way in and the rules always apply.