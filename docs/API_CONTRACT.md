# API Contract

> **Rule:** no endpoint may be added to the backend without updating this file in the same PR.

## Conventions

- **Base path:** `/api/v1` (setting `API_V1_PREFIX`). Breaking changes go to `/api/v2`.
- **Format:** JSON request and response bodies. `Content-Type: application/json`.
- **Naming:** URL paths use lowercase kebab-case plural nouns (`/government/facilities/{facility_id}`). JSON fields use `snake_case`. Timestamps are ISO-8601 UTC. Coordinates are `lat` / `lng` in WGS84 (EPSG:4326).
- **Module prefixes:** `/citizen`, `/evaluator`, `/government`. Shared endpoints such as `/health` sit at the root of v1.
- **Success responses:** return the resource object (or paginated list envelope) directly. No `{data: ...}` wrapper.
- **Error envelope (all errors):**
  ```json
  { "detail": "Human-readable message", "code": "machine_readable_code" }
  ```
  Codes in use:
  - `http_<status>` (e.g. `http_403`, `http_404`, `http_501`)
  - `validation_error` (422)
  - `illegal_issue_transition` (409 — attempted transition not in `ALLOWED_ISSUE_TRANSITIONS`)
  - `transition_note_required` (422 — `resolved` or `dismissed` transition missing non-empty `note`)
  - `missing_verified_recipient` (422 — `/notify` called on a facility without a verified operator email)
  - `unsupported_notification_channel` (422 — e.g. `sms`, which is reserved and not implemented)
  - `internal_error` (500)
- **Pagination:** query params `page` (1-based, default 1) and `page_size` (default 20, max `GOV_MAX_PAGE_SIZE=100`). Response:
  ```json
  { "items": [], "total": 0, "page": 1, "page_size": 20 }
  ```
- **Auth:** `Authorization: Bearer <supabase-access-token>` (Shabaz). All `/api/v1/government/*` routes require `government` or `admin` role via `require_government_user`.
- **Types:** response schemas in `backend/app/schemas/` are mirrored in `frontend/src/lib/api/types.ts` and `frontend/src/lib/api/government.types.ts`.

---

## Implemented endpoints — Health

### `GET /api/v1/health`

Liveness check. No auth.

```json
{
  "status": "ok",
  "app": "Namma Suvidha API",
  "env": "development",
  "version": "0.1.0",
  "timestamp": "2026-10-30T09:45:00.123456Z"
}
```

### `GET /api/v1/health/db`

Database and PostGIS check. **Always HTTP 200**, even when the database is down.

```json
{ "connected": false, "postgis_available": false, "postgis_version": null, "error": "RuntimeError: DATABASE_URL is not configured" }
```

---

## Citizen

### `GET /api/toilets/nearby` (also mounted at `GET /api/v1/toilets/nearby`)

**Owner:** Citizen / Discovery module  
**Auth:** Public (no auth required).  
**Purpose:** Discovers real public toilets around a citizen's GPS coordinates within a configurable radius (`default: 10000`, `max: 10000` metres) by querying the OpenStreetMap Overpass API (`amenity=toilets` across `node`, `way`, and `relation` elements), normalizing tags and center coordinates, computing exact Haversine distance (`distance_meters` and `distance_km`), deduplicating by `(osm_type, osm_id)`, and sorting ascending by distance.

- **Query Parameters:**
  - `latitude` (`float`, required): `-90 <= latitude <= 90`
  - `longitude` (`float`, required): `-180 <= longitude <= 180`
  - `radius` (`int`, optional, default `10000`): `1 <= radius <= 10000` (metres)
- **Error codes:**
  - `422` (`validation_error`): invalid latitude, longitude, or radius (`<= 0` or `> 10000`).
  - `429` (`overpass_rate_limited`): OpenStreetMap Overpass API rate limit reached.
  - `502` (`overpass_unavailable` / `overpass_invalid_response`): upstream Overpass server unavailable or returned malformed payload.
  - `504` (`overpass_timeout`): upstream Overpass query timed out.
- **Success Response (`200 OK`):**
  ```json
  {
    "success": true,
    "origin": {
      "latitude": 12.9716,
      "longitude": 77.5946
    },
    "radius_meters": 10000,
    "total_results": 1,
    "source": "OpenStreetMap",
    "results": [
      {
        "osm_id": 1001,
        "osm_type": "node",
        "name": "Cubbon Park Namma Toilet",
        "latitude": 12.975,
        "longitude": 77.592,
        "distance_meters": 472,
        "distance_km": 0.47,
        "address": {
          "street": "Kasturba Road",
          "city": "Bengaluru",
          "postcode": "560001"
        },
        "tags": {
          "amenity": "toilets",
          "name": "Cubbon Park Namma Toilet",
          "fee": "no",
          "access": "yes",
          "wheelchair": "yes",
          "opening_hours": "24/7",
          "operator": "BBMP"
        }
      }
    ]
  }
  ```

### `POST /api/v1/citizen/facilities/{facility_id}/cleanliness` — **PROPOSED — not implemented in Phase 2**

- **Owner:** Citizen module (Ibrahim + Gaurish) / Rate-limiting & abuse rules: Shabaz.
- **Purpose:** One-tap YES/NO cleanliness response endpoint backing the QR code / web link posted at each facility. Government reads the resulting `CleanlinessResponse` records via `CleanlinessRepository`; Government never writes them.
- **Auth:** Unauthenticated or lightly rate-limited (Shabaz to confirm).
- **Proposed request body:**
  ```json
  {
    "is_clean": true,
    "channel": "qr"
  }
  ```
  (`channel` is `"qr"` or `"web"`; `"iot"` is reserved for future physical button integration.)

---

## Evaluator (`/api/v1/evaluator`) — Implemented in Stage 3

**Owner:** Ibrahim (Evaluator workflow, WebAuthn integration, ID storage & Admin review) + Shabaz (Auth & RLS) + Shubham (45-day cooldown & inspection schema)  
**Auth:** Guarded by `EvaluatorAuthProvider` (`require_authenticated_claims`, `require_evaluator`, `require_approved_evaluator`, and `require_admin`). Preserves `backend/app/core/security.py` and FastAPI `dependency_overrides[get_current_user]`.

### 1. `POST /api/v1/evaluator/register` (`201 Created`)
Registers or updates the authenticated gig-worker evaluator's onboarding profile (`evaluator_status: "pending"`).
- **Auth:** `require_authenticated_claims` (valid JWT + verified email).
- **Request body:** `{ "full_name": "Deepa Krishnan", "phone": "+919845012345", "operating_area": "Jayanagar Ward 170", "preferred_language": "kn" }`

### 2. `GET /api/v1/evaluator/me` (`200 OK`)
Returns the authenticated evaluator's onboarding status, verification status, registered passkey metadata (never raw public keys), and `inspection_access_granted` boolean.
- **Auth:** `require_evaluator`.

### 3. `POST /api/v1/evaluator/documents` (`201 Created`)
Validates magic bytes (`JPEG`, `PNG`, `WEBP`, `PDF` without JavaScript, `<= 5 MB`), stores the identity document in private storage (`evaluator-ids/{evaluator_id}/{verification_id}.{ext}`), and creates a `pending` verification record (or transitions a `rejected` evaluator back to `pending` while scheduling the superseded file for immediate deletion).
- **Auth:** `require_evaluator` (`pending` or `rejected` status only).
- **Request body:** `{ "document_type": "driving_licence", "file_base64": "<base64>", "mime_type": "image/png" }`

### 4. `POST /api/v1/evaluator/passkeys/register/options` (`200 OK`)
Generates a 32-byte single-use WebAuthn registration challenge (`purpose: "registration"`, TTL 300s) and returns `PublicKeyCredentialCreationOptionsJSON`.
- **Auth:** `require_evaluator`.

### 5. `POST /api/v1/evaluator/passkeys/register/verify` (`201 Created`)
Atomically consumes the registration challenge, verifies origin, `rpIdHash`, `UP=1`, `UV=1`, `AT=1`, and COSE public key (`ES256` `-7` or `RS256` `-257`), and stores the credential in `webauthn_credentials`.
- **Auth:** `require_evaluator`.

### 6. `POST /api/v1/evaluator/passkeys/authenticate/options` (`200 OK`)
Generates a single-use WebAuthn authentication or inspection-submission challenge (`purpose: "authentication" | "inspection_submit"`).
- **Auth:** `require_evaluator`.

### 7. `POST /api/v1/evaluator/passkeys/authenticate/verify` (`200 OK`)
Cryptographically verifies a WebAuthn assertion (`clientDataJSON`, `authenticatorData`, `signature`), enforces monotonic `sign_count` (or calibrates `sign_count_initialized=false` legacy credentials on first use), and consumes the challenge.
- **Auth:** `require_evaluator`.

### 8. `DELETE /api/v1/evaluator/passkeys/{credential_id}` (`200 OK`)
Revokes a registered passkey owned by the evaluator (or by an admin).
- **Auth:** `require_evaluator`.

### 9. `GET /api/v1/evaluator/tasks` (`200 OK`)
Lists inspection tasks assigned to the authenticated **approved** evaluator.
- **Auth:** `require_approved_evaluator` (`evaluator_status == "approved"` + active passkey).

### 10. `POST /api/v1/evaluator/tasks/{task_id}/accept` (`200 OK`)
Accepts an assigned task (`assigned -> in_progress`) after verifying ownership and Shubham's 45-day evaluator–toilet cooldown.
- **Auth:** `require_approved_evaluator`.

### 11. `POST /api/v1/evaluator/inspections/submit` (`201 Created`)
Verifies a fresh cryptographic WebAuthn assertion bound to `purpose="inspection_submit"` and `task_id` (rejecting credential-ID-only submissions with `401 webauthn_assertion_incomplete`), enforces idempotency via `idempotency_key`, saves the inspection, marks the task `completed`, and records the 45-day cooldown window.
- **Auth:** `require_approved_evaluator`.

### 12. Admin Evaluator Management Endpoints (`/api/v1/evaluator/admin/*`)
All protected by `require_admin` (`role == "admin"`):
- `GET /api/v1/evaluator/admin/applications` — Filterable list of evaluator applications (`status`, `operating_area`, `search`).
- `GET /api/v1/evaluator/admin/applications/{evaluator_id}` — Detailed evaluator record, verification metadata, passkey metadata, and audit trail.
- `GET /api/v1/evaluator/admin/applications/{evaluator_id}/document` — Generates a 60-second signed preview URL for the private ID document and appends `evaluator.document_previewed` to `audit_logs`.
- `POST /api/v1/evaluator/admin/applications/{evaluator_id}/approve` — Transitions `pending -> approved` (requires uploaded ID document) and schedules 7-day ID retention expiry.
- `POST /api/v1/evaluator/admin/applications/{evaluator_id}/reject` — Transitions `pending -> rejected` (requires non-empty `reason`) and schedules 7-day ID retention expiry.
- `POST /api/v1/evaluator/admin/applications/{evaluator_id}/suspend` — Transitions `approved -> suspended` (requires non-empty `reason`).
- `POST /api/v1/evaluator/admin/applications/{evaluator_id}/reinstate` — Transitions `suspended -> approved` (requires non-empty `reason`).
- `POST /api/v1/evaluator/admin/retention/purge` — Deletes expired raw ID documents from private storage, verifies object removal (`deletion_verified = true`), and logs `evaluator.document_purged`.
- `GET /api/v1/evaluator/admin/audit-logs` — Queries the append-only `audit_logs` repository (`target_type`, `target_id`, `actor_id`, `action`).

---

## Government (`/api/v1/government`) — Implemented in Phase 2

**Owner:** Ibrahim  
**Auth:** Every route is protected by `require_government_user` (`government` or `admin` role). Without Shabaz's `get_current_user` implementation, unauthenticated calls receive `HTTP 501` (`http_501`); authenticated non-government calls receive `HTTP 403` (`http_403`). In `APP_ENV=development` with `GOV_DEV_AUTH_BYPASS=true`, requests succeed with response header `X-Dev-Auth-Bypass: true`.

> **Important note on `triage` / `triage_level`:** Every `triage` object or `triage_level` field returned by these endpoints is a **Government triage classification** (`urgent`, `high`, `normal`, `unranked`) for ordering follow-up work. It is **not** a cleanliness score, **not** a facility score, and **not** a replacement for Shubham's official scoring engine in `app.modules.intelligence`.

### 1. `GET /api/v1/government/overview`

Returns `OverviewStatistics` computed from repositories (all zeros when empty; `facilities_low_usage` and `facilities_cleanliness_unknown` are evaluated across **all** facilities, including facilities with zero responses).

```json
{
  "total_facilities": 0,
  "recommended": 0,
  "needing_attention": 0,
  "unscored": 0,
  "unverified": 0,
  "pending_complaints": 0,
  "active_issues": 0,
  "escalated_issues": 0,
  "resolved_issues": 0,
  "recent_inspections": 0,
  "positive_feedback_count": 0,
  "negative_feedback_count": 0,
  "cleanliness_alerts_last_24h": 0,
  "facilities_low_usage": 0,
  "facilities_cleanliness_unknown": 0,
  "generated_at": "2026-10-30T12:30:00Z",
  "data_source": "memory"
}
```

### 2. `GET /api/v1/government/facilities`

Paginated list of `FacilitySummary`.

- **Query parameters:** `ward`, `verification_status` (`verified`|`unverified`|`pending`), `condition` (`recommended`|`moderate`|`attention`|`unscored`), `stale_only` (bool), `low_usage_only` (bool), `lat`, `lng`, `radius_m`, `page` (default 1), `page_size` (default 20, max 100).

### 3. `GET /api/v1/government/facilities/{facility_id}`

Returns `FacilityDetail` including `responsible_party` (only when `verified`; contact details visible to government/admin only), `latest_inspection`, `official_score` (from `app.modules.intelligence`), `data_quality` flags (`inspection_stale`, `never_inspected`, `missing_operator`, `missing_location`, `low_usage`, `cleanliness_unknown`), `latest_cleanliness_window`, and `triage` (`level`, `reasons`, `responsibility_unverified`, `classification_note`).

- **Errors:** `404` (`http_404`) if `facility_id` does not exist.

### 4. `GET /api/v1/government/facilities/{facility_id}/feedback`

Paginated `CitizenFeedbackItem` list for a facility, with `meta`:

- **Query parameters:** `since` (ISO-8601 datetime), `page`, `page_size`.
- **Response:**
  ```json
  {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20,
    "meta": {
      "sentiment_breakdown": { "positive": 0, "neutral": 0, "negative": 0 },
      "cleanliness_windows": []
    }
  }
  ```
- **Errors:** `404` (`http_404`) if `facility_id` does not exist.

### 5. `GET /api/v1/government/feedback`

Paginated `CitizenFeedbackItem` list across facilities. Every item has `source: "citizen_feedback"` and `age_hours`. Evaluator inspections are never included.

- **Query parameters:** `facility_id`, `ward`, `category`, `sentiment` (`positive`|`neutral`|`negative`), `severity` (1..5), `channel` (`app`|`qr`|`web`|`iot`), `since`, `linked_to_issue` (bool), `page`, `page_size`.

### 6. `GET /api/v1/government/feedback/repeated`

Paginated `RepeatedComplaintCluster` list grouping negative citizen feedback by `(facility_id, category)` within `GOV_REPEAT_WINDOW_DAYS` (14) where `count >= GOV_REPEAT_MIN_COUNT` (3) and `distinct_reporters >= GOV_REPEAT_MIN_REPORTERS` (2).

- **Query parameters:** `facility_id`, `ward`, `page`, `page_size`.

### 7. `POST /api/v1/government/evaluate`

**Synchronous, latest-window-only evaluation:**
1. Processes the single most recent **complete** window aligned to `GOV_CLEAN_WINDOW_MINUTES` (default 60) across **every** facility in `FacilityRepository.list_all_ids()` (including zero-response facilities, which receive `verdict: "insufficient_data"` and `low_usage: true`, never `clean`).
2. **No backfill:** Earlier missed windows are **not** backfilled in this MVP; raw responses remain stored, and `cleanliness.note` explicitly states: `"Processed latest complete window only; earlier missed windows are not backfilled in this MVP."`
3. Creates cleaning issues (`type: "cleaning"`), sends test alert emails when a verified operator email exists and `GOV_CLEAN_AUTO_NOTIFY=true`, and escalates active cleaning issues (`status: "escalated"`, setting `verification_requested_at`) when negativity persists.
4. Runs `detect_maintenance` for non-cleaning `urgent`/`high` triage signals.
5. **Idempotent** per `(facility_id, window_start)` and open issue.

```json
{
  "cleanliness": {
    "window_start": "2026-10-30T11:00:00Z",
    "window_end": "2026-10-30T12:00:00Z",
    "facilities_considered": 5,
    "windows_saved": 5,
    "skipped_existing": 0,
    "clean": 1,
    "needs_cleaning": 2,
    "insufficient_data": 2,
    "low_usage_flagged": 2,
    "alerts_created": 2,
    "alerts_emailed": 1,
    "alerts_without_recipient": 1,
    "escalations": 0,
    "affected_facility_ids": ["fac-majestic-01", "fac-krpuram-05"],
    "affected_issue_ids": ["iss-a1b2c3d4e5", "iss-f6g7h8i9j0"],
    "note": "Processed latest complete window only; earlier missed windows are not backfilled in this MVP."
  },
  "maintenance": {
    "evaluated_at": "2026-10-30T12:30:00Z",
    "facilities_considered": 5,
    "issues_created": 1,
    "existing_issues_noted": 0,
    "created_issue_ids": ["iss-m1n2o3p4q5"]
  }
}
```

### 8. `GET /api/v1/government/cleanliness/windows`

Paginated `CleanlinessWindow` history.

- **Query parameters:** `facility_id`, `since`, `verdict` (`clean`|`needs_cleaning`|`insufficient_data`), `page`, `page_size`.

### 9. `GET /api/v1/government/issues`

Paginated `MaintenanceIssue` list.

- **Query parameters:** `status` (`open`|`alert_sent`|`acknowledged`|`escalated`|`resolved`|`dismissed`), `type` (`cleaning`|`maintenance`), `triage_level` (`urgent`|`high`|`normal`|`unranked`), `ward`, `facility_id`, `page`, `page_size`.

### 10. `GET /api/v1/government/issues/{issue_id}`

Returns a single `MaintenanceIssue` with full append-only `history` (`IssueAuditEntry[]`) and `notifications` (`NotificationRecord[]`).

- **Errors:** `404` (`http_404`) if `issue_id` does not exist.

### 11. `POST /api/v1/government/issues/{issue_id}/notify`

Sends or re-sends the structured alert email to the facility's verified operator via the configured email provider (`TestEmailProvider` by default). Transitions `open -> alert_sent` on success; never auto-resolves an issue. Provider delivery failures do not raise 500 — they return `HTTP 200` with `status: "failed"` and `provider_message`.

- **Optional request body:** `{ "channel": "email" }` (`"sms"` returns `422 unsupported_notification_channel`).
- **Errors:** `404` (`http_404`) if issue/facility not found; `422` (`missing_verified_recipient`) if facility lacks a verified operator email.

### 12. `POST /api/v1/government/issues/{issue_id}/transition`

Transitions an issue along `ALLOWED_ISSUE_TRANSITIONS` and appends an `IssueAuditEntry`. When `to_status == "acknowledged"`, also marks the latest notification `acknowledged`.

- **Request body:**
  ```json
  {
    "to_status": "acknowledged",
    "note": "Sanitation supervisor dispatched cleaning crew"
  }
  ```
- **Errors:** `404` (`http_404`) if issue not found; `409` (`illegal_issue_transition`) if transition is not permitted; `422` (`transition_note_required`) if `to_status` is `resolved` or `dismissed` and `note` is empty/whitespace.
