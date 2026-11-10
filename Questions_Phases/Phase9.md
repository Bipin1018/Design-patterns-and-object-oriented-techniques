# Phase 9 — Decorator questions

**Pattern / focus:** Decorator.

**Read first:** [Guide 09](../../materials/guides/09-decorator.md) · [Requirements](requirements.md)

## How to answer

- Use your own wording. Do not paste teaching-example types (for example HTTP client wrappers) as if they were your greenhouse classes.
- When a question asks about *this application*, refer to `ActuatorPort`, policy decorators, and `actuator_execution_log` from the lab.
- Short answers are fine when the question is narrow. Write a few sentences when it asks you to explain or compare.
- Write each answer inside the matching **Your Answer** note. Replace the placeholder; leave the question text unchanged.

## A. Pattern

1. State the intent of Decorator in plain language. Why is stacking wrappers a flexible alternative to a combinatorial explosion of subclasses (`LoggingRetryMaxRuntimeActuator`, …)?

> [!NOTE]
> ***Your Answer***
>
> Decorator adds extra behaviour to an object by wrapping it in another object with the same interface. The wrapper does its own small job and then passes the call on, or refuses to.
>
> With subclasses, every mix of extras needs its own class: logging only, max run time only, both, both plus retry, and so on. Each new rule doubles the number of combinations. With wrappers, each rule is written once as its own class, and you choose the mix when you build the chain. Adding a rule means one new wrapper, not a new subclass for every combination.

2. Name the participants (**component**, **concrete component**, **decorator**, **concrete decorators**). What interface does every decorator present to the caller, and why must that match the wrapped component?

> [!NOTE]
> ***Your Answer***
>
> The component is the interface everyone shares, which is `ActuatorPort` in our app. The concrete component is the real object doing the work, `SimulationActuatorAdapter`. A decorator is a class that implements `ActuatorPort` and holds another `ActuatorPort` inside it. Our concrete decorators are `LoggingActuatorDecorator` and `MaxRunTimeActuatorDecorator`.
>
> Every decorator offers the same `apply(device_id, command, payload)` method. It has to match, because the caller should not know or care what it is talking to. If a wrapper changed the method, every caller would need to know which wrapper it had, and you could no longer stack them in any order you like.

3. **Order matters.** Using logging and retry (or logging and max-run-time) as an example, explain how wrapping A around B can change what you observe compared with wrapping B around A.

> [!NOTE]
> ***Your Answer***
>
> We wrap logging around max run time. When max run time blocks a command, it raises an error, and logging is still outside and catches it, so a row with `success=false` and `["maxRunTime", "logging"]` is written.
>
> If we swapped them, max run time would sit outside and block the call before it ever reached logging. The blocked attempt would leave no row at all, and the dashboard would never show it.
>
> With retry, the order decides how many rows you get. Logging outside retry writes one row per request, however many tries it took. Logging inside retry writes one row per try.

## B. This phase of the application

4. What is `ActuatorPort` here, and which **at least two** decorators did you stack around the real adapter (for example logging and max run-time)? Where is the chain wired (composition root / factory), and why not inside the HTTP router?

> [!NOTE]
> ***Your Answer***
>
> `ActuatorPort` is the interface for telling an actuator to do something. It has one method, `apply(device_id, command, payload)`. The real adapter behind it is `SimulationActuatorAdapter`.
>
> We stacked two decorators around it: `LoggingActuatorDecorator` on the outside and `MaxRunTimeActuatorDecorator` in the middle. The chain is built in one place, `ActuatorExecutionService.port_for`, which picks the real adapter for the device and wraps it.
>
> It is not in the router because the router should only handle HTTP. If the policy checks lived there, any other caller, like the Phase 10 commands or a test, could skip them. Building the chain in the service means everyone gets the same rules.

5. Max run-time can **short-circuit**: the inner adapter is never called. Why must a blocked attempt still produce a row in `actuator_execution_log` with `success=false` and the policy named in `policy_applied`?

> [!NOTE]
> ***Your Answer***
>
> A blocked attempt is still something that happened. If only successful commands were logged, nobody could tell that someone tried to use the pump and was refused, or why.
>
> The row with `success=false`, `["maxRunTime", "logging"]` and `Max run time exceeded` shows exactly which rule stopped it. That is useful for the user looking at the dashboard and for anyone debugging later.

6. How does max run-time know the actuator has been running too long (for example `actuator_states.updated_at` from Phase 8)? Why is that data from **State**, not something the decorator should invent as a second lifecycle?

> [!NOTE]
> ***Your Answer***
>
> The decorator reads the stored state from `actuator_states` through `ActuatorStateRepository`. `updated_at` changes on every transition, so while the state is `running`, it shows when the pump started. If the state is `running` and `updated_at` is at least 30 minutes ago, the command is blocked.
>
> The lifecycle already belongs to the State pattern from Phase 8. If the decorator kept its own "started at" time, there would be two versions of the truth, and they would drift apart, for example after a restart or a change made through the transition endpoint. The decorator only reads the state; it never changes it.

7. `GET /api/actuators/executions` feeds the dashboard execution log. Why persist attempts in the database instead of only printing to stdout? What should the UI show after a blocked attempt and a refresh?

> [!NOTE]
> ***Your Answer***
>
> Printed logs disappear when the container restarts. They can't be queried, and the dashboard can't read them. Storing each attempt in `actuator_execution_log` means it survives a restart, the API can list it, and the UI can show it.
>
> After a blocked attempt and a refresh, the newest row in the execution log shows the device, a `failed` badge, the policies `maxRunTime` and `logging`, and the message `Max run time exceeded`. It is still there after refreshing, because it comes from the database.

## C. Compare, contrast, and scenarios

8. Contrast Decorator with **Adapter**. Both wrap. One **keeps** the interface and **adds** behaviour; the other **changes** the interface and **translates**. Which is which in this greenhouse (Phase 9 vs Phase 5)?

> [!NOTE]
> ***Your Answer***
>
> Decorator keeps the interface and adds behaviour. In Phase 9, the logging and max run time wrappers are `ActuatorPort` on the outside and `ActuatorPort` on the inside. They only add logging and a rule.
>
> Adapter changes the interface and translates. In Phase 5, the sensor adapters take what a vendor device or MQTT message sends and turn it into our own `Reading`, so the rest of the app only sees one format.

9. Contrast Decorator with **inheritance** of combined policies. How does composition let you add or remove a policy without a new subclass for every combination?

> [!NOTE]
> ***Your Answer***
>
> With inheritance, the mix of rules is fixed when you write the class. Logging plus max run time needs its own subclass, and adding retry means more subclasses for every combination.
>
> With composition, each rule is one wrapper and the mix is decided in `port_for`. To add a rule, we write one class and add one line to the chain. To remove a rule, we delete that line. The adapter and the other wrappers don't change.

10. A classmate's decorator changes the method signature "a little" (extra required argument, different return type). Another ignores wrap order and cannot explain whether logging runs once per logical call or per inner attempt. Explain why each is a trap.

> [!NOTE]
> ***Your Answer***
>
> If a decorator changes the signature, it is no longer the same interface. Callers that expect `ActuatorPort` would break or need to know about that wrapper, and you can't freely stack it with the others anymore. That breaks the whole point of the pattern.
>
> Ignoring wrap order is a trap because the order changes what happens. In our app, if logging were inside max run time, blocked attempts would never be logged. With a retry, logging outside writes one row per request and logging inside writes one row per try. If you can't say which you have, you can't trust the numbers in the log.