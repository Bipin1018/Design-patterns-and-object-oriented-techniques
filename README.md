# Smart Greenhouse

A monitoring and control system for a smart greenhouse, built as a series of
design-pattern phases. The backend is a FastAPI application over PostgreSQL,
the frontend is a React dashboard, and the three tiers run together under
Docker Compose.

Each phase introduces one design pattern and the feature that needs it. The
patterns are applied to real parts of the system — sensors, devices,
locations, automation and actuators — rather than shown as isolated examples.

## Contents

- [Technology](#technology)
- [Architecture](#architecture)
- [Getting started](#getting-started)
- [URLs](#urls)
- [Phases](#phases)
- [Database](#database)
- [API overview](#api-overview)
- [Quality checks](#quality-checks)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)

## Technology

| Layer | Stack |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic |
| Database | PostgreSQL 16 |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, React Router |
| API reference | Scalar (Swagger and ReDoc are disabled) |
| Tooling | Docker Compose, pytest, ruff, oxlint |

## Architecture

The backend follows a layered structure. Dependencies point inwards only.

| Layer | Responsibility | Depends on |
|---|---|---|
| `domain` | Entities, rules and ports. Plain Python with no framework code | Nothing |
| `application` | Use cases, DTOs and mappers | `domain` |
| `infrastructure` | Database models, repositories, adapters, settings | `domain` |
| `interfaces/api` | HTTP routers that map errors to status codes | `application` |

Business rules live in the domain. Routers stay thin: they call a service and
translate domain errors into HTTP responses. The frontend never decides what is
legal; it displays what the API returns. All backend calls from the frontend
go through `frontend/src/services/api.ts`.

## Getting started

### Prerequisites

| Tool | Version |
|---|---|
| Docker Desktop | Current |
| Git | Any |
| Python | 3.11+ (only for running the backend outside Docker) |
| Node.js | 20 LTS (only for running the frontend outside Docker) |

### First-time setup

From the repository root:

```powershell
copy .env.example .env
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

`.env` is gitignored and holds the database credentials. The host port for
PostgreSQL comes from `POSTGRES_PORT`. Change it if another PostgreSQL already
uses 5432 on your machine.

Check that all three containers are running and the database is healthy:

```powershell
docker compose ps
docker compose exec backend alembic current
```

`alembic current` should end with `(head)`.

### Sample data

To get a set of devices to work with, provision a simulation kit (two sensors
and two actuators):

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/devices/provision?family=simulation" -Method Post
```

Locations and zones can then be created from the Configuration section of the
dashboard.

### Daily use

```powershell
docker compose up -d      # start
docker compose down       # stop, data is kept
```

The backend runs with `--reload` and the source folders are bind-mounted, so
code changes are picked up without rebuilding. `docker compose down -v` also
deletes the database volume; run `alembic upgrade head` again afterwards.

## URLs

| What | Where |
|---|---|
| Dashboard | http://localhost:5173/dashboard |
| API reference (Scalar) | http://localhost:8000/scalar |
| Health check | http://localhost:8000/health |
| OpenAPI schema | http://localhost:8000/openapi.json |

## Phases

| Phase | Pattern | Feature |
|---|---|---|
| 1 | — | Three-tier skeleton and health check |
| 2 | Factory Method | Sensor creation |
| 3 | Abstract Factory | Matching device families |
| 4 | Builder | Locations, zones and device placement |
| 5 | Adapter | Sensor readings from different sources |
| 6 | Strategy | Pluggable watering decisions |
| 7 | Facade | Single location overview |
| 8 | State | Actuator lifecycle |
| 9 | Decorator | Actuator policies and execution log |

Each pattern has a short write-up in [`docs/patterns/`](docs/patterns/), and the
answers to each phase's questions are in [`Questions_Phases/`](Questions_Phases/).

### Phase 1 — Skeleton

Sets up all three tiers and proves each one can reach the next. The backend
exposes `GET /health`, which reports whether the API can reach PostgreSQL.
When the database is down it returns `{"status": "degraded", "db": "fail"}`
with HTTP 200 instead of failing, and it recovers by itself. The dashboard
header shows API and database status side by side. Alembic is configured with
an empty baseline migration.

### Phase 2 — Factory Method

**Problem:** moisture and light sensors need different units, sampling
intervals and thresholds. Without a pattern, that choice becomes a chain of
`if` statements in the route.

**Solution:** `SensorCreator` defines one method, `create_sensor`. Each
concrete creator builds one kind of sensor with its own defaults. Callers ask
`get_creator` for a creator by name and never choose a class themselves. An
unknown type returns 400 and nothing is saved.

- **Adds:** the `devices` table, `GET` and `POST /api/sensors`, and the sensor
  list on the dashboard.
- **Key files:** `domain/sensors/creators.py`, `application/sensors/service.py`.
- **Doc:** [`factory-method.md`](docs/patterns/factory-method.md)

### Phase 3 — Abstract Factory

**Problem:** the greenhouse runs either on simulated devices or on real
hardware. Devices must come as a matching set; a simulated pump cannot be
paired with a real sensor.

**Solution:** `DeviceFamilyFactory` creates a complete kit of two sensors and
two actuators. `SimulationDeviceFactory` and `EdgeHardwareFactory` decide what
goes into their kit. The family factories reuse the Phase 2 creators for the
sensors. The domain `Device` entity is kept separate from the `DeviceDto` JSON
shape, with a mapper between them.

- **Adds:** the `device_family` column, `GET /api/devices` with family and role
  filters, `POST /api/devices/provision?family=...`, and the device list with a
  family switcher.
- **Key files:** `domain/devices/family_factory.py`,
  `application/devices/family_service.py`.
- **Doc:** [`abstract-factory.md`](docs/patterns/abstract-factory.md)

### Phase 4 — Builder

**Problem:** a location has a name and any number of zones, each with
thresholds and a schedule. Some rules, such as unique zone names, can only be
checked once every part is present.

**Solution:** `LocationConfigBuilder` collects the parts through chained calls
and validates everything in `build()`. An invalid configuration raises
`ConfigurationError` before anything is written. Device placement is a separate
update through `ZoneAssignmentService`. The client sends only `zone_id`, and
`location_id` is copied from the zone so the two cannot disagree.

- **Adds:** the `locations` and `zones` tables, `zone_id` and `location_id` on
  devices, location and zone endpoints, `PATCH /api/devices/{id}/zone`, and the
  configuration wizard.
- **Key files:** `domain/locations/config_builder.py`,
  `application/locations/config_service.py`.
- **Doc:** [`builder.md`](docs/patterns/builder.md)

### Phase 5 — Adapter

**Problem:** every sensor source reports in its own format. A simulated sensor
has no protocol, a vendor reports moisture as an integer out of 1000 with
millisecond timestamps, and an MQTT device publishes on its own schedule.

**Solution:** `SensorPort` promises one `Reading` for a device. The simulation,
vendor and MQTT adapters each translate their source into that same shape, and
`get_sensor_port` picks the right one. Adapters translate only; they do not
make decisions. `ActuatorPort` and `SimulationActuatorAdapter` are defined here
as the actuator side of the same idea. A background sampler records readings
for each device on its own interval.

- **Adds:** the `sensor_readings` table, sampling columns on devices,
  `POST /api/sensors/{id}/read`, `GET /api/sensors/{id}/readings`,
  `PATCH /api/devices/{id}/sampling`, and Read now, source badges and interval
  controls on the sensor cards.
- **Key files:** `infrastructure/adapters/sensors/`,
  `application/readings/service.py`, `application/readings/sampler.py`.
- **Doc:** [`adapter.md`](docs/patterns/adapter.md)

### Phase 6 — Strategy

**Problem:** when to water is a matter of policy. Watering late saves water,
watering early keeps plants safer, and each site should be able to choose and
change its approach.

**Solution:** each algorithm implements one interface: given a zone's
readings and thresholds, return an action and a reason. The conservative
strategy waters at the low threshold. The aggressive strategy waters from the
middle of the band, and sooner in strong light. A location stores only the
strategy key. The service loads the facts and asks the strategy; it contains
no threshold logic itself.

- **Adds:** the `automation_rules` table, `GET /api/automation/strategies`,
  `GET` and `PUT /api/locations/{id}/automation`,
  `POST /api/locations/{id}/automation/evaluate`, and the strategy panel.
- **Key files:** `domain/automation/strategy.py`,
  `application/automation/service.py`.
- **Doc:** [`strategy.md`](docs/patterns/strategy.md)

### Phase 7 — Facade

**Problem:** the dashboard overview needs a location, its zones, assigned
devices, latest readings, the saved strategy and a recommendation. Collecting
these piece by piece spreads the knowledge across the router and the frontend.

**Solution:** `LocationOverviewFacade.get_overview` is the single entry point.
It gathers everything with a fixed number of queries and reuses the Phase 6
evaluate service for the recommendation. No new table is needed.

- **Adds:** `GET /api/locations/{id}/overview` and the overview panel.
- **Key files:** `application/overview/facade.py`,
  `infrastructure/persistence/overview_repository.py`.
- **Doc:** [`facade.md`](docs/patterns/facade.md)

### Phase 8 — State

**Problem:** what an actuator may do depends on what it is doing now. A running
pump cannot be started again, and a faulted one must be reset first. Boolean
flags and scattered `if` checks let these rules drift apart.

**Solution:** `ActuatorContext` holds the current state and checks every move
against one transition table. The five states are off, idle, running, error
and maintenance. An illegal move raises `IllegalTransitionError`, the API
returns 409, and the stored state is unchanged. Each device response carries
`allowed_commands`, so the UI never has to work out the rules itself. State is
persisted, so it survives a restart.

- **Adds:** the `actuator_states` table, `state` and `allowed_commands` on
  devices, `GET /api/devices/{id}/state`, `POST /api/devices/{id}/transition`,
  and state badges on the device list.
- **Key files:** `domain/actuators/state.py`, `domain/actuators/context.py`,
  `application/devices/state_service.py`.
- **Doc:** [`state.md`](docs/patterns/state.md)

### Phase 9 — Decorator

**Problem:** commands to an actuator need rules around them: every attempt
should be recorded, and a command should be refused once an actuator has been
running too long. Putting these checks in the router or inside the adapter
mixes concerns and is easy to bypass.

**Solution:** each rule is a wrapper that implements `ActuatorPort` and holds
another `ActuatorPort`. The chain is built in one place,
`ActuatorExecutionService.port_for`:

    LoggingActuatorDecorator
      → MaxRunTimeActuatorDecorator
        → SimulationActuatorAdapter

Max run time blocks a command when the actuator's stored state is `running`
and `updated_at` is at least 30 minutes old. In that case the adapter is never
called. Logging is outermost, so it records blocked attempts as well as
successful ones.

| Outcome | success | policy_applied | message |
|---|---|---|---|
| Applied | true | `["logging"]` | null |
| Blocked | false | `["maxRunTime", "logging"]` | Max run time exceeded |

- **Adds:** the `actuator_execution_log` table,
  `GET /api/actuators/executions`, a demo `POST /api/actuators/{id}/apply`
  (409 when blocked), and the execution log in the Controls section.
- **Key files:** `infrastructure/adapters/actuators/logging_decorator.py`,
  `infrastructure/adapters/actuators/max_runtime_decorator.py`,
  `application/actuators/execution_service.py`.
- **Doc:** [`decorator.md`](docs/patterns/decorator.md)

## Database

All schema changes are Alembic migrations in `backend/alembic/versions/`.

| Table | Phase | Purpose |
|---|---|---|
| `devices` | 2, extended in 3–5 | Sensors and actuators, family, placement, sampling |
| `locations` | 4 | Sites |
| `zones` | 4 | Areas within a location, with moisture thresholds |
| `sensor_readings` | 5 | Every recorded reading and its source |
| `automation_rules` | 6 | The chosen strategy per location |
| `actuator_states` | 8 | Current lifecycle state per actuator |
| `actuator_execution_log` | 9 | Every attempt to apply an actuator command |

Foreign keys from readings, states and execution rows to `devices` use
`ON DELETE CASCADE`.

## API overview

The full reference, with request and response schemas, is at
http://localhost:8000/scalar.

| Area | Endpoints |
|---|---|
| Health | `GET /health` |
| Sensors | `GET`, `POST /api/sensors` · `POST /api/sensors/{id}/read` · `GET /api/sensors/{id}/readings` |
| Devices | `GET /api/devices` · `POST /api/devices/provision` · `PATCH /api/devices/{id}/zone` · `PATCH /api/devices/{id}/sampling` |
| Actuator state | `GET /api/devices/{id}/state` · `POST /api/devices/{id}/transition` |
| Locations | `GET /api/locations` · `POST /api/locations/config` · `GET /api/locations/{id}/config` · `DELETE /api/locations/{id}` |
| Zones | `POST /api/locations/{id}/zones` · `PATCH`, `DELETE /api/locations/{id}/zones/{zone_id}` · `GET .../zones/{zone_id}/devices` |
| Automation | `GET /api/automation/strategies` · `GET`, `PUT /api/locations/{id}/automation` · `POST /api/locations/{id}/automation/evaluate` |
| Overview | `GET /api/locations/{id}/overview` |
| Actuators | `GET /api/actuators/executions` · `POST /api/actuators/{id}/apply` |

Error conventions: 400 for invalid input, 404 for a missing resource, 409 for
a request that conflicts with the current state (an illegal transition or a
blocked command).

## Quality checks

Run these before every commit:

```powershell
docker compose exec backend ruff check src/ tests/
docker compose exec backend pytest tests -q
docker compose exec backend alembic check
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm run lint
```

Unit tests for the domain (creators, factories, builder, adapters, strategies,
state machine, decorators) run without a database. The API tests need the
stack running. They create their own devices and delete them afterwards.

## Project layout

```text
├── docker-compose.yml          PostgreSQL, backend and frontend
├── .env.example                Copy to .env; never commit .env
├── docs/patterns/              One write-up per pattern
├── Questions_Phases/           Answers to each phase's questions
├── backend/
│   ├── alembic/versions/       Migrations
│   ├── tests/                  Unit and API tests
│   └── src/
│       ├── domain/             Entities, rules and ports
│       │   ├── sensors/        Creators, readings, sensor port
│       │   ├── devices/        Device entity, family factories, sampling
│       │   ├── locations/      Location config builder
│       │   ├── automation/     Strategies
│       │   └── actuators/      Ports, states, policies
│       ├── application/        Services, DTOs, mappers, facade
│       ├── infrastructure/
│       │   ├── adapters/       Sensor adapters, actuator adapter and decorators
│       │   └── persistence/    ORM models and repositories
│       ├── interfaces/api/     HTTP routers
│       └── main.py             App, CORS, sampler, Scalar
└── frontend/src/
    ├── services/api.ts         The only place that calls the backend
    ├── components/             Devices, configuration, overview, actuators
    ├── features/               Sensors and automation
    └── pages/                  Home and dashboard
```

## Troubleshooting

**The dashboard shows the database as down.** Run `docker compose ps` and
check that `greenhouse-postgres` is healthy. Check that `DATABASE_URL` uses the
`postgresql+psycopg://` prefix.

**Port 5432 is already in use.** Another PostgreSQL is running locally. Set
`POSTGRES_PORT` in `.env` to a free port, such as 5433, and restart with
`docker compose up -d`.

**A table is missing after a reset.** Run
`docker compose exec backend alembic upgrade head`.

**`alembic check` reports new operations.** A model in `models.py` changed
without a migration. Generate one with
`docker compose exec backend alembic revision --autogenerate -m "<name>"`,
review it, then upgrade.

**`ModuleNotFoundError: No module named 'src'` outside Docker.** Run Uvicorn
from `backend/`, or install the backend with `pip install -e ".[dev]"`.