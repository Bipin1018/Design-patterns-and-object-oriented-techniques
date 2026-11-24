# Phase 11 — Observer questions

**Pattern / focus:** Observer.

**Read first:** [Guide 11](../../materials/guides/11-observer.md) · [Requirements](requirements.md)

## How to answer

- Use your own wording. Do not paste teaching-example types (for example live auction bids) as if they were your greenhouse classes.
- When a question asks about _this application_, refer to the event bus, alerts, publishers, and the event feed from the lab.
- Short answers are fine when the question is narrow. Write a few sentences when it asks you to explain or compare.
- Write each answer inside the matching **Your Answer** note. Replace the placeholder; leave the question text unchanged.

## A. Pattern

1. State the intent of Observer in plain language. What is a **one-to-many** dependency here, and why must the subject notify dependents **without** knowing their concrete classes?

> [!NOTE]
> **_Your Answer_**
>
> When something happens, one object announces it and anyone interested can react. In our app a single `ReadingCreated` can reach several listeners: the moisture check now, and the dashboard socket in Phase 12.
>
> `ReadingIngest` only talks to the bus, so it has no idea who is listening. We can add a new reaction later without opening the reading code at all.

2. Name the participants (**subject / event bus**, **observer / subscriber**, **concrete observers**, **event**, **publisher**). What does `subscribe` / `unsubscribe` / `publish` (or `notify`) each do? This example’s `EventBus` implements `subscribe` and `publish` only.

> [!NOTE]
> **_Your Answer_**
>
> - Subject: `EventBus`
> - Subscriber: any handler the bus calls with an event
> - Concrete observers: `MoistureThresholdSubscriber` and `AlertPersistenceSubscriber`
> - Events: `ReadingCreated`, `ThresholdCrossed`, `CommandFailed`, `ActuatorStateChanged`, `AlertCreated`
> - Publishers: `ReadingIngest`, `CommandService`, `ActuatorStateService`
>
> `subscribe` registers a handler for one event type, and `publish` calls every handler for that type in the order they were added. `unsubscribe` would take a handler off the list. We left it out because our handlers are set up once when the app starts and never change.

3. When should you use Observer, and when should you skip it (only one listener forever; or you need a strict multi-step workflow with guaranteed order)?

> [!NOTE]
> **_Your Answer_**
>
> It's a good fit when other parts of the app need to react to something and the code where it happens shouldn't care who they are.
>
> If there will only ever be one listener, a direct call is simpler. I'd also avoid it for steps that must run in a fixed order, where a failure has to stop everything after it. Our bus just logs a failing handler and keeps going, so it can't promise that.

## B. This phase of the application

4. Give at least two **domain events** you publish in this lab, including `reading.created` (only when `tracking_enabled` is true), a threshold-crossed event, command-failed, and `ActuatorStateChanged`. The persistence subscriber stores `state.changed` only when that state is `error`. Who publishes `reading.created`, and why do a manual read, the simulation sampler, and MQTT translation share that one ingest publish? Why must a publisher **not** import the alerts repository or the UI?

> [!NOTE]
> **_Your Answer_**
>
> - `reading.created`: a reading was saved and tracking is on
> - `threshold.crossed`: moisture dropped below the zone's low threshold
> - `command.failed`: an allowed command failed, e.g. "Max run time exceeded"
> - `state.changed`: an actuator's state was saved (it only becomes an alert for `error`)
>
> `ReadingIngest` publishes `reading.created`. Manual reads, the sampler and MQTT all finish in its `_store` method, so the tracking rule and the publish live in one place and can't drift apart.
>
> If a publisher imported the alerts repository or the UI, it would depend on the things listening to it. Any change to alerts would then mean editing the reading code as well.

5. What does `AlertPersistenceSubscriber` (or your equivalent) do when it handles an event? Name the three stored rows: `threshold.crossed` / `warning` / `Moisture below zone low`, `command.failed` / `warning` / the failure message, and `state.changed` / `critical` / `Actuator entered error`. Why do alerts live in the `alerts` table so the event feed still shows them after a **refresh**?

> [!NOTE]
> **_Your Answer_**
>
> It writes one active row to `alerts`, using the device, location and zone from the event, and then publishes `AlertCreated`.
>
> | Event | Severity | Message |
> |---|---|---|
> | `threshold.crossed` | warning | Moisture below zone low |
> | `command.failed` | warning | the failure message |
> | `state.changed` (error only) | critical | Actuator entered error |
>
> Anything kept only in React state is gone after a refresh. Since the alerts are rows in the database, the feed just loads them again.

6. The dashboard Event feed **polls** `GET /api/alerts` every 5 seconds in this phase. `services/realtime.ts` is only a **stub**. Why is full WebSocket **not** required in this phase? What should Phase 12 plug into so you do **not** re-implement pub/sub inside socket handlers? Phase 12 subscribes a dashboard socket to this same bus, and the example publishes `AlertCreated` after each insert for that socket.

> [!NOTE]
> **_Your Answer_**
>
> This phase is about getting the pattern right in the backend. Polling every 5 seconds is enough to show stored alerts, and a socket would mostly add connection handling.
>
> In Phase 12 the socket should become one more subscriber on the same `EventBus`. It listens for `AlertCreated` and passes it on to the browser. That way the socket code keeps no listener lists of its own, and the publishers stay as they are.

7. Describe the must-demo path: a **tracked** low-moisture reading leads to an alert row that appears in the feed after poll. Which objects collaborate (reading pipeline → bus → subscriber → API → UI), and which object must **not** write the alert directly? What is stored, and what is not published, when `tracking_enabled` is false?

> [!NOTE]
> **_Your Answer_**
>
> 1. `ReadingIngest` saves a tracked 0.10 reading from a sensor on Bench 1 and publishes `ReadingCreated`.
> 2. `MoistureThresholdSubscriber` sees that 0.10 is under Bench 1's low of 0.20 and publishes `ThresholdCrossed`.
> 3. `AlertPersistenceSubscriber` saves the warning row.
> 4. `EventFeed` polls `GET /api/alerts` and the warning shows up.
>
> `ReadingIngest` never writes the alert itself. With tracking off, the reading is still saved, but nothing is published, so no alert gets created.

## C. Compare, contrast, and scenarios

8. Contrast Observer with **Facade**. Facade simplifies **calling into** a subsystem. Observer **fans out** notifications after something happened. How do both appear in this greenhouse (Phase 7 overview vs this phase)?

> [!NOTE]
> **_Your Answer_**
>
> You call a Facade when you want data back. With Observer, something has already happened and the news goes out to whoever is listening, with no reply expected.
>
> In Phase 7 the dashboard calls `GET /api/locations/{id}/overview`, and one facade gathers devices, readings and the strategy into a single response. In this phase a saved reading or a failed command goes onto the bus, and the subscribers deal with it on their own.

9. Contrast Observer with **Command**. Command captures **intent to act**. Observer propagates **outcomes**. How can `execute()` publish an event without the command class knowing who persists alerts?

> [!NOTE]
> **_Your Answer_**
>
> A command is a request, like "stop the pump". An event describes what happened afterwards, like "the command failed".
>
> In our code `CommandService` runs `execute()` and publishes `CommandFailed` when it fails. The only thing it hands that event to is the bus. Which subscriber saves the alert is decided in `event_bus.py`, so the command side never imports `AlertRepository`.

10. One subscriber throws during `notify` / `publish` and aborts the loop, so later subscribers never run. Why is that a trap? What should the bus do so a failing alert writer does not block metrics (or later WebSocket) subscribers?

> [!NOTE]
> **_Your Answer_**
>
> If one handler crashes, every handler after it is skipped, and the request fails even though the data was already saved.
>
> Our bus runs each handler inside `try/except`. When one fails it logs the error and moves on, so a broken alert writer doesn't stop the others.