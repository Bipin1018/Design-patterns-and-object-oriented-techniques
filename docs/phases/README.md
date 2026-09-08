# Phases

The project is built in phases. Each phase adds one design pattern to a working
stack, so the repository is runnable at the end of every phase.

| Phase | Focus | Adds |
|-------|-------|------|
| 1 | Skeleton — no pattern | Compose + PostgreSQL, FastAPI `/health`, Scalar, Alembic baseline, React shell |
| 2 | Factory Method | `devices` table, sensor creators, `/api/sensors`, fills the Sensors dashboard section |

Later phases fill the remaining dashboard sections: configuration, automation,
overview, controls and events.

## Reading order

Start with the requirements file for the phase you are on, implement it, then
answer that phase's questions. The guided check is a safety net, not a solution.

- `phase-01/requirements.md` · `phase-01/guided-check.md` · `phase-01/questions.md`
- `phase-02/requirements.md` · `phase-02/guided-check.md`

## What Phase 1 leaves in place

Phase 2 should not need a repository restructure. It inherits:

- Layered backend packages (`domain`, `application`, `infrastructure`, `interfaces/api`).
- A configured Alembic environment whose URL comes from application settings.
  Set `target_metadata` in `alembic/env.py` once ORM models exist.
- A typed frontend API client in `frontend/src/services/api.ts`.
- Stable dashboard section ids to target: `overview`, `sensors`, `configuration`,
  `automation`, `controls`, `events`.
