# Namma Suvidha — Public Toilets You Can Actually Trust

AI-assisted public sanitation platform. **Team Agentics** · Alliance ONE Hackathon 2026 ·
Problem Statement **CS/26-0018 – AI for Citizen Well-Being**.

> **Status: Phase 0 foundation + Phase 2 Government Monitoring backend complete.**
> Both apps start and talk over HTTP, and all 12 `/api/v1/government/*` endpoints are implemented and tested.
> See [What is implemented](#what-is-implemented-in-phase-0--phase-2).

## Team and ownership

| Member   | Responsibility |
|----------|----------------|
| Ibrahim  | Project integration, repository structure, Government Monitoring backend; sole merger to `main` |
| Shubham  | Database schema & migrations, AI logic, scoring algorithms, intelligence interfaces |
| Shabaz   | Authentication & security (Supabase Auth, role guards, biometrics) |
| Gaurish  | UI/UX, design system, Tailwind theme, components |
| Abhishta | *To be confirmed:* seed data, test fixtures, demo tooling, QA |

Full directory-level ownership: [docs/INTEGRATION_BOUNDARIES.md](docs/INTEGRATION_BOUNDARIES.md).

## Stack

React 18 + TypeScript + Vite + Tailwind CSS v4 + React Router + Axios · Python 3.11+ + FastAPI ·
PostgreSQL + PostGIS (SQLAlchemy 2 + psycopg 3 + GeoAlchemy2 + Alembic) · Supabase Auth & Storage ·
Leaflet + OpenStreetMap · Gemini API. *Supabase, Leaflet and Gemini are not integrated yet.*

## Repository layout

```
.
├── backend/            FastAPI app (one API for all three modules)
├── frontend/           React app (one SPA for all three modules)
├── docs/               Architecture, API contract, DB, boundaries, environment
├── scripts/            Bash helpers: dev-backend.sh, dev-frontend.sh, check-health.sh
├── docker-compose.yml  OPTIONAL local PostGIS
└── README.md
```

## Prerequisites

- Node.js ≥ 18 (tested on 24.11) and npm
- Python ≥ 3.11 (tested on 3.11.0)
- Optional: PostgreSQL 15/16 with PostGIS, **or** Docker for `docker-compose.yml`
- Bash (Git Bash / WSL / macOS / Linux) to use `scripts/*.sh`. On Windows you can use the PowerShell commands below instead.

## Local setup

### 1. Database (optional in Phase 0)

The backend starts **without** a database: `/api/v1/health/db` will then report `connected: false`.

```bash
docker compose up -d db          # PostGIS 16 on localhost:5432, creds in backend/.env.example
```

Without Docker: install PostgreSQL + PostGIS, then create user `namma`, password `namma_dev_password`
and database `namma_suvidha`, or edit `DATABASE_URL` in `backend/.env`. See [docs/DATABASE.md](docs/DATABASE.md).

### 2. Backend

```bash
./scripts/dev-backend.sh         # creates .venv, installs deps, copies .env, runs uvicorn on :8000
```

Windows (PowerShell):

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### 3. Frontend

```bash
./scripts/dev-frontend.sh        # npm install if needed, copies .env, runs Vite on :5173
```

Windows (PowerShell):

```powershell
cd frontend
npm install
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm run dev
```

Open http://localhost:5173. The landing page shows live API and database status.

### 4. Check health

```bash
./scripts/check-health.sh
# Windows:
curl.exe http://localhost:8000/api/v1/health
curl.exe http://localhost:8000/api/v1/health/db
```

## Tests and lint

```bash
# backend (venv active, inside backend/)
ruff check .
pytest -q

# frontend (inside frontend/)
npm run lint
npm run test
npm run build
npm run format:check
```

## What is implemented in Phase 0 & Phase 2

### Phase 0 (Foundation)
- FastAPI app factory with CORS, a consistent error envelope `{detail, code}` and structured logging
- `GET /api/v1/health` and `GET /api/v1/health/db`. The DB check never returns 500.
- Lazy SQLAlchemy engine, `get_db()` dependency, and a PostGIS version check
- Alembic wired to `DATABASE_URL`, with **zero** migrations
- React SPA: router, app shell, landing page, three module pages, 404 page, live `BackendStatus`
- Typed env access, an Axios client with error normalisation, and Tailwind v4

### Phase 2 (Government Monitoring Backend & Feedback-Driven Cleaning — Owner: Ibrahim)
- **12 protected endpoints under `/api/v1/government`** behind `require_government_user` (`overview`, `facilities`, `facilities/{id}`, `facilities/{id}/feedback`, `feedback`, `feedback/repeated`, `evaluate`, `cleanliness/windows`, `issues`, `issues/{id}`, `issues/{id}/notify`, `issues/{id}/transition`).
- **Feedback-driven cleaning (`POST /api/v1/government/evaluate`):** synchronous evaluation of the latest complete window (`GOV_CLEAN_WINDOW_MINUTES`, default 60m) across **every** facility (including zero-response facilities, which receive `insufficient_data` and `low_usage=true`, never `clean`), operator email alert creation, escalation to physical verification (`verification_requested_at`), and idempotent re-evaluation. **Note: earlier missed windows are not backfilled in this MVP.**
- **Government triage classification (`urgent`/`high`/`normal`/`unranked`):** consumes Shubham's official score via `FacilityScoreProvider` without computing any score, clearly labelled as a triage classification in code, schemas, docs, and frontend types.
- **Issue lifecycle & notifications:** single transition table (`open`, `alert_sent`, `acknowledged`, `escalated`, `resolved`, `dismissed`), append-only audit history, and `TestEmailProvider` (`[TEST EMAIL — NOT DELIVERED]`).
- **Simulated in Phase 2 (by design):** in-memory repositories starting empty (`GOV_REPOSITORY_BACKEND=memory` until Shubham's ORM models land), `TestEmailProvider` outbox, optional dev-only auth bypass (`GOV_DEV_AUTH_BYPASS=true` in `development` only), and hidden dev fixtures loader (`POST /api/v1/government/_dev/load-fixtures`).
- **Frontend handoff:** typed client and interfaces in `frontend/src/lib/api/government.ts` and `government.types.ts`.

## What is NOT implemented yet

Database schema/models/migrations · Supabase JWT verification in `core/security.py` · Citizen & Evaluator endpoints ·
maps (Leaflet UI) · Gemini / AI search & official scoring engine in `modules/intelligence` ·
background scheduler or missed-window backfill for `/evaluate` · SMS notifications · payments · biometrics.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/API_CONTRACT.md](docs/API_CONTRACT.md)
- [docs/GOVERNMENT_MONITORING.md](docs/GOVERNMENT_MONITORING.md)
- [docs/proposals/GOVERNMENT_DATA_REQUIREMENTS.md](docs/proposals/GOVERNMENT_DATA_REQUIREMENTS.md)
- [docs/DATABASE.md](docs/DATABASE.md)
- [docs/INTEGRATION_BOUNDARIES.md](docs/INTEGRATION_BOUNDARIES.md)
- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)
