# Observer — Phase 11

## Why

When something happens in the greenhouse, other parts of the app may need to
react. A dry bench should raise an alert, and so should a failed command or a
broken actuator. If the code that saves a reading also had to create alerts, it
would need changing every time we added a new reaction.

With Observer, the code that does the work only announces what happened. Other
parts listen and decide for themselves what to do. The announcer doesn't know
who is listening.

## The parts

- **Event bus (the subject):** keeps a list of listeners for each kind of event.
  `subscribe` adds a listener and `publish` calls them in order.
- **Events:** small, read-only records of something that happened, such as a
  reading being saved or a command failing. Each one says which device, location
  and zone it is about. A device with no zone has none.
- **Publishers:** the reading, command and actuator-state services. They publish
  events and know nothing about alerts.
- **Subscribers (the observers):** one checks moisture readings against the
  zone's low threshold. The other saves alerts.
- **Composition root:** one place at startup that creates the bus and connects
  the subscribers. Everything else uses that same bus.

## Flow

1. A reading is saved. If tracking is on for that device, the reading service
   publishes `reading.created`.
2. The moisture subscriber checks that reading. If it is a moisture reading from
   a sensor in a zone, and the value is below the zone's low threshold, it
   publishes `threshold.crossed`.
3. A command fails. The command service publishes `command.failed`.
4. An actuator's state is saved. The state service publishes `state.changed`.
5. The alert subscriber listens for the last three events and saves an alert:

| Event | Severity | Message |
|---|---|---|
| threshold.crossed | warning | Moisture below zone low |
| command.failed | warning | why it failed, e.g. Max run time exceeded |
| state.changed (only when the new state is error) | critical | Actuator entered error |

## Rules

- Every reading, whether manual, sampled or from MQTT, passes through one place
  that saves it and then publishes the event.
- If tracking is off for a device, its reading is saved but not announced.
- Events are published only after the data is saved.
- If one listener fails, the others still run, and the user's request still
  succeeds.
- Moisture must be strictly below the threshold. A rejected command is not an
  alert.

## Where alerts go

Alerts are stored in the database, so they survive a restart or a page refresh.
`GET /api/alerts` lists them newest first, and can filter by status, location,
zone and time. The dashboard's event feed asks for new alerts every 5 seconds.

If a device or zone is deleted later, its alerts stay. The link is just cleared.

## Observer vs WebSocket

This bus works inside the backend. It is how one part of the code tells another
that something happened. A WebSocket sends messages to the browser. In Phase 12
the WebSocket becomes one more subscriber on this bus, so new alerts reach the
dashboard straight away. None of the publishers need to change.