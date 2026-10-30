# modules/government

**OWNER:** Ibrahim (Government Monitoring backend & project integration)

## Purpose

Implements the Government Monitoring backend for Namma Suvidha:
1. Facility monitoring (filtering, detail, latest inspection, official score consumption, data-quality flags).
2. Government overview statistics computed directly from repositories (zeros when empty).
3. Citizen feedback monitoring and repeated-complaint cluster detection (strictly separated from evaluator inspections).
4. **Feedback-driven cleaning**: hourly aggregation of one-tap YES/NO cleanliness responses over **every** facility, configurable thresholds, operator email alerts, escalation to physical verification, and a 24-hour low-usage guard so silence is never treated as cleanliness.
5. Minimal maintenance and cleaning issue lifecycle with append-only audit history.
6. Test email notifications via `TestEmailProvider`.

## Layer rules

- **`app/api/v1/government.py`**: HTTP layer only. Validates query/body parameters, calls `services/*`, and returns `app/schemas/government.py` models. Contains zero business logic.
- **`services/*`**: Deterministic domain logic. Depends **only** on the `typing.Protocol` interfaces in `interfaces.py`, domain read models in `domain.py`, and `GovernmentSettings` in `config.py`.
- **`domain.py`**: Pydantic v2 read models returned by the API. These are **not** SQLAlchemy ORM models.
- **`repositories/*`**: Selected by `GOV_REPOSITORY_BACKEND=memory|sql` (default `memory`). If `sql` is requested before Shubham's ORM models exist, `repositories/sql.py` raises `GovernmentSchemaPendingError` and the factory logs a `WARNING` and falls back to `memory`.
- **`providers/*`**:
  - `scores.py` (`IntelligenceScoreProvider`): Consumes the official facility score from `app.modules.intelligence` (Shubham). Government **never** computes a facility or cleanliness score.
  - `email.py` (`TestEmailProvider`): Logs `[TEST EMAIL — NOT DELIVERED]` and appends to an in-memory outbox.

## How to switch to the SQL repository once Shubham's schema lands

1. Review and align `docs/proposals/GOVERNMENT_DATA_REQUIREMENTS.md` with Shubham's ORM models.
2. Implement the four protocols (`FacilityRepository`, `FeedbackRepository`, `CleanlinessRepository`, `IssueRepository`) inside `repositories/sql.py`, mapping ORM rows into `domain.py` read models and using `ST_DWithin` for radius filtering.
3. Set `GOV_REPOSITORY_BACKEND=sql` in `backend/.env`. Zero changes are needed in `services/*` or `api/v1/government.py`.
