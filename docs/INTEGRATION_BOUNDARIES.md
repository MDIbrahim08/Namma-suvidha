# Integration Boundaries

Who owns what, what they can change freely, and what needs coordination.

## Ownership map

| Path | Owner | May change freely | Requires coordination |
|------|-------|-------------------|-----------------------|
| `/` (README, `.gitignore`, `.editorconfig`, `docker-compose.yml`) | Ibrahim | Wording, ignore rules | New infrastructure (needs team agreement) |
| `docs/API_CONTRACT.md` | Ibrahim (custodian), everyone | Adding your own endpoints in the same PR as the code | Changing conventions or existing endpoints |
| `docs/DATABASE.md` | Shubham | Table register, migration notes | — |
| `docs/*` (others) | Ibrahim | Clarifications | Changes to the rules in this file |
| `scripts/` | Ibrahim | Fixes | Behaviour changes |
| `backend/app/main.py`, `api/router.py` | Ibrahim | Registering routers | Middleware, error format |
| `backend/app/core/config.py` | Ibrahim | Adding a setting (plus `.env.example` and `docs/ENVIRONMENT.md`) | Renaming or removing settings |
| `backend/app/core/security.py` | Shabaz | Everything | Changing the `get_current_user` signature or the user object shape |
| `backend/app/db/session.py` | Ibrahim | Fixes | Engine/session behaviour (talk to Shubham) |
| `backend/app/db/base.py`, models, `backend/alembic/` | Shubham | Models and migrations | Any change other modules depend on |
| `backend/app/api/v1/health.py` | Ibrahim | — | — |
| `backend/app/api/v1/citizen.py`, `modules/citizen/` | Ibrahim (+ Gaurish as consumer) | Endpoints and logic | Contract changes |
| `backend/app/api/v1/evaluator.py`, `modules/evaluator/` | Ibrahim + Shabaz | Endpoints and logic | Contract changes; auth/biometric flows |
| `backend/app/api/v1/government.py`, `modules/government/` | Ibrahim | Endpoints, services, in-memory repositories, test email provider | Contract changes; `repositories/sql.py` (with Shubham); `dependencies.py::extract_roles` (with Shabaz) |
| `docs/GOVERNMENT_MONITORING.md` | Ibrahim | Module architecture & cleaning workflow docs | Cross-module handoff rules |
| `docs/proposals/GOVERNMENT_DATA_REQUIREMENTS.md` | Ibrahim (proposer), Shubham (approver) | Clarifications | Approving / turning into ORM models & migrations (Shubham) |
| `backend/app/modules/intelligence/` | Shubham | AI, scoring, fraud, allocation, cooldown | Function signatures used by other modules (`get_facility_score(facility_id)` consumed by `government/providers/scores.py`) |
| `backend/app/schemas/` | Author of the endpoint | New schemas (`government.py` — Ibrahim) | `common.py` envelopes (Ibrahim) |
| `backend/tests/` | Author of the code under test; Abhishta (QA) | New tests (`tests/government/` — Ibrahim) | Shared fixtures in `conftest.py` |
| `frontend/src/app/` (router, layout) | Ibrahim (structure), Gaurish (visuals) | Gaurish: styling | Adding/removing routes (Ibrahim) |
| `frontend/src/components/ui/`, `index.css` theme | Gaurish | Everything | Breaking component props |
| `frontend/src/components/status/` | Ibrahim | Fixes | — |
| `frontend/src/config/env.ts` | Ibrahim | Adding variables (plus `.env.example` and docs) | Renaming variables |
| `frontend/src/lib/api/` | Ibrahim | Adding endpoint functions/types (`government.ts`, `government.types.ts`) | `client.ts` behaviour |
| `frontend/src/lib/supabase.ts`, auth interceptor in `client.ts` | Shabaz | Everything | Exposed auth API used by pages |
| `frontend/src/features/citizen/` | Ibrahim + Gaurish | Pages and components | — |
| `frontend/src/features/evaluator/` | Ibrahim + Shabaz (+ Gaurish UI) | Pages and components | Route guards |
| `frontend/src/features/government/` | Ibrahim (+ Gaurish UI) | Pages and components | — |
| `frontend/src/pages/` | Ibrahim (+ Gaurish UI) | Copy and styling | — |
| Seed data, fixtures, demo tooling (future `backend/seeds/`, `scripts/demo/`) | Abhishta (TBC) | See below | Seed data must follow Shubham's schema |

## Abhishta — reserved scope

**Suggested scope (to be confirmed): seed data, test fixtures, demo script, QA.**

Reserved locations, not created yet: `backend/seeds/`, `backend/tests/fixtures/`,
`frontend/src/test/fixtures/` and `scripts/demo/`. Seed data must only target tables that exist in Shubham's migrations.
It must never appear in production UI as if it were real data.

## Working agreement

1. **Branches:** `feature/<owner>-<topic>`, e.g. `feature/shabaz-supabase-auth`. Fixes use `fix/<owner>-<topic>`.
2. **Only Ibrahim merges to `main`**, via pull request. No direct pushes.
3. **API contract travels with code:** a PR that adds or changes an endpoint must update `docs/API_CONTRACT.md` and the mirrored TS types.
4. **No secrets in commits.** Real values go in `.env` only, which is git-ignored.
5. **One `.env.example` update per new variable.** Add it to the right `.env.example` and to `docs/ENVIRONMENT.md` in the same PR.
6. **Green before merge:** `ruff check`, `pytest`, `npm run lint`, `npm run test` and `npm run build` must pass.
7. **No mock data in the UI.** Pages show real API data or an honest empty/pending state.
8. **Schema changes go through Shubham.**

