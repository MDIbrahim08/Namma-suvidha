# Environment Variables

Real values live in `backend/.env` and `frontend/.env`. Both are git-ignored. Templates: the `.env.example` files.

## Backend (`backend/.env`)

### Core application settings

| Variable | Purpose | Required? | Required from |
|----------|---------|-----------|---------------|
| `APP_NAME` | Display name returned by `/health` | Optional (default `Namma Suvidha API`) | — |
| `APP_ENV` | `development` or `production` | Optional (default `development`) | — |
| `API_V1_PREFIX` | Base path for v1 routes | Optional (default `/api/v1`) | — |
| `BACKEND_HOST` | Bind host for uvicorn | Optional (default `0.0.0.0`) | — |
| `BACKEND_PORT` | Bind port for uvicorn | Optional (default `8000`) | — |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins | Optional (default `http://localhost:5173`) | Required in production |
| `DATABASE_URL` | SQLAlchemy URL, `postgresql+psycopg://...` (auto-normalizes `postgresql://` and disables prepared statements for Supabase Supavisor port 6543) | Optional in Phase 0/2 (app starts without it) | When SQL repo enabled |
| `SUPABASE_URL` | Supabase project URL (`https://YOUR_PROJECT_REF.supabase.co`) | Optional (placeholder) | Phase 1 (auth/storage) |
| `SUPABASE_ANON_KEY` | Supabase public key | Optional (placeholder) | Phase 1 |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase admin key. **Server only, never expose to React.** | Optional (placeholder) | Phase 1 (storage/admin) |
| `SUPABASE_JWT_SECRET` | Verifies Supabase JWTs | Optional (placeholder) | Phase 1 (auth) |
| `GEMINI_API_KEY` | Gemini API access | Optional (placeholder) | Phase 1+ (AI features) |
| `OPENROUTER_API_KEY` | OpenRouter API key (**backend only**) | Optional (placeholder) | When live OpenRouter transcription/analysis is invoked |
| `OPENROUTER_BASE_URL` | OpenRouter API base URL | Optional (default `https://openrouter.ai/api/v1`) | — |
| `AUDIO_TRANSCRIPTION_MODEL` | OpenRouter speech-to-text model ID | Optional (default `deepgram/nova-3`) | — |
| `COMPLAINT_ANALYSIS_MODEL` | OpenRouter chat completion model ID for structured complaint extraction | Optional (default `google/gemini-3.8-flash`) | — |
| `OPENROUTER_TIMEOUT_SECONDS` | HTTP timeout in seconds for OpenRouter requests | Optional (default `30.0`) | — |
| `VOICE_MAX_AUDIO_BYTES` | Max accepted audio payload size in bytes | Optional (default `10485760` = 10 MB) | — |
| `LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING`/`ERROR` | Optional (default `INFO`) | — |

### Government Monitoring settings (`GOV_*`, owner: Ibrahim)

| Variable | Purpose | Default | Required from |
|----------|---------|---------|---------------|
| `GOV_REPOSITORY_BACKEND` | Repository implementation (`memory` or `sql`) | `memory` | Optional |
| `GOV_ALLOWED_ROLES` | Comma-separated roles allowed on `/api/v1/government/*` | `government,admin` | Optional |
| `GOV_DEV_AUTH_BYPASS` | Development-only auth bypass (`true`/`false`; **refused at startup when `APP_ENV != development`**) | `false` | Optional (dev only) |
| `GOV_DEV_FIXTURES_ENABLED` | Enables hidden `POST /api/v1/government/_dev/load-fixtures` in development | `false` | Optional (dev only) |
| `GOV_MAX_PAGE_SIZE` | Maximum `page_size` on government paginated endpoints | `100` | Optional |
| `GOV_SCORE_RECOMMENDED_MIN` | Minimum official score for `recommended` band | `70.0` | Optional |
| `GOV_SCORE_ATTENTION_MAX` | Maximum official score for `attention` band and `high` triage | `40.0` | Optional |
| `GOV_INSPECTION_STALE_DAYS` | Days after which latest inspection is flagged `inspection_stale` (reporting threshold, independent of Shubham's 45-day cooldown) | `45` | Optional |
| `GOV_RECENT_INSPECTION_DAYS` | Window in days for `recent_inspections` overview counter | `7` | Optional |
| `GOV_PENDING_FEEDBACK_WINDOW_DAYS` | Window in days for unlinked negative `pending_complaints` | `30` | Optional |
| `GOV_REPEAT_WINDOW_DAYS` | Lookback window in days for repeated complaint clusters | `14` | Optional |
| `GOV_REPEAT_MIN_COUNT` | Minimum negative complaints in `(facility_id, category)` for a cluster | `3` | Optional |
| `GOV_REPEAT_MIN_REPORTERS` | Minimum distinct reporters required for a cluster | `2` | Optional |
| `GOV_CLEAN_WINDOW_MINUTES` | Aligned window length in minutes for feedback-driven cleaning | `60` | Optional |
| `GOV_CLEAN_MIN_RESPONSES` | Minimum YES/NO responses required for a valid window verdict and 24h usage | `3` | Optional |
| `GOV_CLEAN_NEGATIVE_RATIO` | `no_count / total` threshold triggering `needs_cleaning` | `0.5` | Optional |
| `GOV_CLEAN_ESCALATE_AFTER_WINDOWS` | Subsequent negative windows after an active alert before escalating to physical verification | `1` | Optional |
| `GOV_CLEAN_LOW_USAGE_HOURS` | Lookback hours over which `< GOV_CLEAN_MIN_RESPONSES` flags `low_usage` and `cleanliness_unknown` | `24` | Optional |
| `GOV_CLEAN_AUTO_NOTIFY` | Automatically send test alert email when a verified operator exists | `true` | Optional |
| `GOV_EMAIL_PROVIDER` | `test` (logs `[TEST EMAIL — NOT DELIVERED]`) or `smtp` (reserved, raises if selected) | `test` | Optional |

### Evaluator policy reference settings (`EVAL_POLICY_*`, optional)

| Variable | Purpose | Default | Required from |
|----------|---------|---------|---------------|
| `EVAL_POLICY_MAX_DAILY_INSPECTIONS_PER_EVALUATOR` | Optional policy cap reference for Evaluator module | `None` | Optional |
| `EVAL_POLICY_RISK_BASED_REINSPECTION_ENABLED` | Optional policy flag for consuming `verification_requested_at` escalations | `None` | Optional |

## Frontend (`frontend/.env`)

All `VITE_*` values are **embedded in the public JS bundle**. Never put secrets here.

| Variable | Purpose | Required? | Required from |
|----------|---------|-----------|---------------|
| `VITE_API_BASE_URL` | Backend origin, e.g. `http://localhost:8000` (no `/api/v1`) | **Required.** The app throws at startup if it is missing. | Phase 0 |
| `VITE_APP_NAME` | Display name in the header | Optional (default `Namma Suvidha`) | — |
| `VITE_SUPABASE_URL` | Supabase project URL | Optional (empty) | Phase 1 (auth) |
| `VITE_SUPABASE_ANON_KEY` | Supabase public anon key | Optional (empty) | Phase 1 (auth) |

## Adding a variable

Add it to `Settings` / `GovernmentSettings` (backend) or `config/env.ts` + `vite-env.d.ts` (frontend), then to the `.env.example` file and to this table, all in the same PR.
