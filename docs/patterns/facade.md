# Facade — Phase 7

## Why one entry point

The dashboard overview needs data from several parts of the app. Instead of
the router or the frontend collecting it piece by piece, there is one entry
point:

    GET /api/locations/{location_id}/overview

The route calls only `LocationOverviewFacade.get_overview(location_id)`, and
the dashboard panel makes only this one call. If a part behind the facade
changes, only the facade needs updating.

## What the facade hides

- **Locations and zones** — the location and every zone in it, including empty ones
- **Assigned devices** — devices with this `location_id` and a `zone_id`; unassigned devices are left out
- **Readings** — the newest `sensor_readings` row for each assigned device, from any source
- **Saved strategy** — the strategy key saved in Phase 6, or null if none is saved

## Where it is in the code

    application/overview/dto.py
    application/overview/facade.py
    infrastructure/persistence/overview_repository.py
    interfaces/api/overview_deps.py
    interfaces/api/overview.py
    frontend/src/components/overview/OverviewPanel.tsx
    tests/test_overview_api.py

## How the recommendation is made

`last_recommendation` is computed on every GET by calling the existing
automation `evaluate` service. It is not stored in a new table, so it always
matches the current readings.

If no strategy is saved, `strategy_key` and `last_recommendation` are both
null and `evaluate` is not called.

## Query shape

Each GET runs:

1. One load of the location and its zones
2. One query for the assigned devices
3. One query for the newest reading of all those devices
4. One read of the saved strategy key
5. `evaluate`, only when a key is saved

Readings are not queried once per device. `evaluate` may still look up
moisture once per zone. That stays inside the automation service so the
strategy logic is not copied into the facade.

## Database

No new table was required. The optional view was skipped because the
existing tables are enough.