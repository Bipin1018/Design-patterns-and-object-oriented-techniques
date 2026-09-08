# Smart Greenhouse

Monitoring and control for a smart greenhouse: a FastAPI backend over PostgreSQL with a React dashboard.

Phase 1 is the skeleton. It stands up all three tiers and proves each one reaches the next; there are no business tables and no design pattern yet.

## Prerequisites

| Tool | Minimum version | Verify |
|------|-----------------|--------|
| Python | 3.11+ | `python --version` |
| Node.js | 20 LTS | `node --version` |
| Docker Desktop | current | `docker --version` |
| Git | any | `git --version` |

## First-time setup

Run these once after cloning. Commands are shown for PowerShell; on macOS or Linux use `cp` instead of `copy` and `source .venv/bin/activate` instead of the `Activate.ps1` script.

**1. Environment file**

```powershell
copy .env.example .env
```

`.env` is gitignored. Both Docker Compose and the backend read it, so the credentials only need to be correct in one place.

**2. Start PostgreSQL**

```powershell
docker compose up -d
docker compose ps
```

Wait until the `db` service reports `healthy`.

**3. Install the backend**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

**4. Apply the database baseline**

```powershell
alembic upgrade head
alembic current
```

`alembic current` should print `001_baseline (head)`. The migration creates no tables — only Alembic's own `alembic_version` bookkeeping table. That is deliberate: it proves the migration toolchain reaches PostgreSQL before Phase 2 adds real tables.

**5. Install the frontend**

```powershell
cd ..\frontend
npm install
```

The frontend defaults to `http://localhost:8000`. To point it elsewhere, copy `frontend/.env.example` to `frontend/.env.local` and edit `VITE_API_BASE_URL`.

## Daily start

Three terminals, in this order.

```powershell
# 1. Database — from the repository root
docker compose up -d

# 2. Backend — from backend/, with the virtualenv active
python -m uvicorn src.main:app --reload

# 3. Frontend — from frontend/
npm run dev
```

Stop the database with `docker compose down`. Add `-v` only if you want to discard the stored data, which means re-running `alembic upgrade head` afterwards.

## URLs

| What | Where |
|------|-------|
| Dashboard | http://localhost:5173/dashboard |
| API root | http://localhost:8000/ |
| Health check | http://localhost:8000/health |
| API reference (Scalar) | http://localhost:8000/scalar |
| OpenAPI schema | http://localhost:8000/openapi.json |

Swagger (`/docs`) and ReDoc (`/redoc`) are disabled on purpose — Scalar is the documented reference for this project.

## Checking that it works

With all three running, the health badge in the dashboard header shows API and Database side by side, both green. `GET /health` returns:

```json
{ "status": "ok", "db": "ok" }
```

Stop the database and it becomes `{"status": "degraded", "db": "fail"}` with an HTTP 200 — the endpoint reports the problem rather than failing outright, and it recovers on its own once Postgres is back.

## Layout

```text
├── docker-compose.yml      PostgreSQL 16 with a healthcheck and named volume
├── .env.example            Copy to .env; never commit .env
├── backend/
│   ├── alembic/            Migration environment; URL comes from app settings
│   └── src/
│       ├── domain/         Business entities            (empty until Phase 2)
│       ├── application/    Use cases                    (empty until Phase 2)
│       ├── infrastructure/ Settings, engine, DB check
│       ├── interfaces/api/ HTTP routers
│       └── main.py         FastAPI app, CORS, Scalar
└── frontend/src/
    ├── services/api.ts     The only place that calls the backend
    ├── components/         Layout and health badge
    └── pages/              Home and dashboard
```

The layer rule: `domain` depends on nothing, `application` may use `domain`, `infrastructure` holds everything technical, and HTTP routing lives only in `interfaces`.

## Quality tooling

```powershell
# From backend/, with the virtualenv active
ruff check .
ruff format .
pytest

# From frontend/
npm run lint
npm run build
```

The backend tests pass whether or not PostgreSQL is running: they assert the health contract, not the state of your machine.

## Troubleshooting

**`ModuleNotFoundError: No module named 'src'`** — you started Uvicorn from the wrong directory. Run it from `backend/`, or reinstall with `pip install -e .` so `src` is importable from anywhere.

**Health badge shows Database red** — the API is up but Postgres is not. Check `docker compose ps` and confirm `DATABASE_URL` in `.env` uses the `postgresql+psycopg://` prefix, not a raw `postgres://` DSN.

**Port 5432 already in use** — another Postgres is running locally. Change `POSTGRES_PORT` in `.env` and update the port in `DATABASE_URL` to match.

## Phases

See [docs/phases/README.md](docs/phases/README.md) for the phase order and what each one adds. Phase 2 introduces the Factory Method pattern, the `devices` table and `/api/sensors`.
