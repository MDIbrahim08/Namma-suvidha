# PROPOSED — AWAITING SHUBHAM'S APPROVAL — NOT IMPLEMENTED AS SCHEMA

**Author:** Ibrahim (Government Monitoring module owner)  
**Target Owner:** Shubham (Database Schema, Migrations, and Intelligence owner)  
**Status:** Proposed data contract only. Zero tables, ORM models, or Alembic migrations have been created by the Government module.

---

## 1. Purpose & Ownership Boundaries

The Government Monitoring module (`backend/app/modules/government/`) currently runs against `interfaces.py` (`FacilityRepository`, `FeedbackRepository`, `CleanlinessRepository`, `IssueRepository`) backed by `repositories/memory.py`. Once Shubham approves and creates the SQLAlchemy 2.x ORM models and Alembic migrations, `repositories/sql.py` will map those ORM rows into the Pydantic v2 read models in `domain.py`.

### Write Ownership Summary

| Entity | Read by Government? | Written by Government? | Primary Write Owner |
| :--- | :---: | :---: | :--- |
| **Facilities** | Yes | No (read-only) | Admin / Seed / Shubham |
| **Responsible Parties (Operators/Authorities)** | Yes | No (read-only) | Admin / Seed / Shubham |
| **Evaluator Inspections** | Yes (latest summary) | No (read-only) | Evaluator module |
| **Citizen Feedback** | Yes | No (read-only) | Citizen module |
| **Cleanliness Responses (One-tap YES/NO)** | Yes | No (read-only) | Citizen module (`POST /api/v1/citizen/facilities/{id}/cleanliness`) |
| **Cleanliness Windows** | Yes | **Yes** | Government module (`POST /api/v1/government/evaluate`) |
| **Maintenance & Cleaning Issues** | Yes | **Yes** | Government module |
| **Issue Audit Entries** | Yes | **Yes (append-only)** | Government module |
| **Notification Records** | Yes | **Yes** | Government module |

---

## 2. Proposed Entities & Fields Required by Government

### 2.1 Facilities (`facilities`) — *Read-Only to Government*
| Field | Proposed Type | Nullable? | Why Government Needs It |
| :--- | :--- | :---: | :--- |
| `id` | `UUID` or `VARCHAR` (PK) | No | Primary lookup & foreign key target; `list_all_ids()` iterates every facility during `/evaluate` and overview low-usage checks |
| `name` | `VARCHAR(200)` | No | Displayed in facility lists, detail, complaint clusters, and alert emails |
| `ward` | `VARCHAR(100)` | No | Required filter on `/facilities`, `/feedback`, `/feedback/repeated`, and `/issues` |
| `address` | `TEXT` | Yes | Included in facility detail and operator alert email payload |
| `location` / `lat`, `lng` | `GEOGRAPHY(POINT, 4326)` + `FLOAT` | Yes | Radius filter (`ST_DWithin`), `missing_location` data-quality flag, and email payload |
| `verification_status` | Enum (`verified`, `unverified`, `pending`) | No | Filters `/facilities`, drives `unverified` overview counter and `responsibility_unverified` flag |
| `responsible_party_id` | FK → `responsible_parties.id` | Yes | Links facility to its operator/authority |

**Indexes needed:** `(ward)`, `(verification_status)`, `GIST (location)`.

### 2.2 Responsible Parties (`responsible_parties`) — *Read-Only to Government*
| Field | Proposed Type | Nullable? | Why Government Needs It |
| :--- | :--- | :---: | :--- |
| `id` | `UUID` or `VARCHAR` (PK) | No | Primary key |
| `name` | `VARCHAR(150)` | No | Displayed to government officers |
| `organization` | `VARCHAR(200)` | Yes | Displayed to government officers |
| `role_title` | `VARCHAR(150)` | Yes | Displayed to government officers |
| `email` | `VARCHAR(254)` | Yes | Recipient for cleaning/maintenance alert emails (government-only; redacted for citizens) |
| `phone` | `VARCHAR(40)` | Yes | Contact number (government-only; redacted for citizens) |
| `verified` | `BOOLEAN` | No | Alerts are only emailed when both facility and responsible party are `verified` |

### 2.3 Evaluator Inspections (`inspections`) — *Read-Only to Government*
| Field | Proposed Type | Nullable? | Why Government Needs It |
| :--- | :--- | :---: | :--- |
| `id` | `UUID` or `VARCHAR` (PK) | No | Referenced by ID in `latest_inspection` and notification `evidence_reference_ids` |
| `facility_id` | FK → `facilities.id` | No | Lookup latest inspection per facility |
| `evaluator_id` | `UUID` or `VARCHAR` | Yes | Displayed in `InspectionSummary` |
| `inspected_at` | `TIMESTAMPTZ` | No | Computes `inspection_stale` (>45 days) and `recent_inspections` (<=7 days) |
| `checklist_passed` | `BOOLEAN` | Yes | Summary status |
| `summary_note` | `TEXT` | Yes | Displayed in `FacilityDetail.latest_inspection` |
| `evidence_ids` | `JSONB` / array of IDs | No | Referenced by ID only in alert email payloads |

**Indexes needed:** `(facility_id, inspected_at DESC)`.

### 2.4 Citizen Feedback (`citizen_feedback`) — *Read-Only to Government*
*(Strictly separate from `inspections` — never merged in any aggregate.)*
| Field | Proposed Type | Nullable? | Why Government Needs It |
| :--- | :--- | :---: | :--- |
| `id` | `UUID` or `VARCHAR` (PK) | No | Primary key |
| `facility_id` | FK → `facilities.id` | No | Filter & cluster grouping |
| `ward` | `VARCHAR(100)` (or via join) | Yes | Filter on `/feedback` and `/feedback/repeated` |
| `category` | Enum (`FeedbackCategory`, 10 values) | No | Filter & repeated-complaint grouping `(facility_id, category)` |
| `sentiment` | Enum (`positive`, `neutral`, `negative`) | No | Overview counts, per-facility sentiment breakdown, and negative cluster filtering |
| `severity` | `SMALLINT` (1..5) | No | Filter on `/feedback` |
| `channel` | Enum (`app`, `qr`, `web`, `iot`) | No | Filter on `/feedback` (`iot` reserved) |
| `comment` | `TEXT` | Yes | Displayed in feedback list |
| `reporter_hash` | `VARCHAR(128)` | Yes | Counts `distinct_reporters` in `repeated_clusters` (requires `>= 2` distinct reporters) |
| `linked_issue_id` | FK → `maintenance_issues.id` | Yes | Filters `linked_to_issue` and counts unlinked `pending_complaints` in last 30 days |
| `evidence_ids` | `JSONB` / array of IDs | No | Referenced by ID only in alert emails |
| `created_at` | `TIMESTAMPTZ` | No | Computes `age_hours`, `since` filter, and 14-day repeat window |

**Indexes needed:** `(facility_id, created_at DESC)`, `(sentiment, created_at DESC)`, `(facility_id, category, created_at)` for repeated-complaint clusters.

### 2.5 Cleanliness Responses (`cleanliness_responses`) — *Written by Citizen, Read by Government*
| Field | Proposed Type | Nullable? | Why Government Needs It |
| :--- | :--- | :---: | :--- |
| `id` | `UUID` or `VARCHAR` (PK) | No | Primary key |
| `facility_id` | FK → `facilities.id` | No | Hourly window aggregation and 24-hour low-usage count per facility |
| `is_clean` | `BOOLEAN` | No | One-tap YES (`true`) / NO (`false`) response |
| `channel` | Enum (`qr`, `web`, `app`, `iot`) | No | Channel tracking (`qr`/`web` for one-tap; `iot` reserved) |
| `respondent_hash` | `VARCHAR(128)` | Yes | Optional deduplication / abuse prevention hash |
| `created_at` | `TIMESTAMPTZ` | No | Window slicing `[window_start, window_end)` and 24h low-usage check |

**Indexes needed:** `(facility_id, created_at)` — critical for both hourly window aggregation and the 24-hour low-usage count across all facilities.

### 2.6 Cleanliness Windows (`cleanliness_windows`) — *Written by Government*
*(Stores one row per facility per evaluated window, including `insufficient_data` rows for zero-response facilities.)*
| Field | Proposed Type | Nullable? | Why Government Needs It |
| :--- | :--- | :---: | :--- |
| `facility_id` | FK → `facilities.id` | No | Composite unique key `(facility_id, window_start)` for idempotency |
| `window_start` | `TIMESTAMPTZ` | No | Start of aligned window |
| `window_end` | `TIMESTAMPTZ` | No | End of aligned window |
| `yes_count` | `INTEGER` | No | Positive count |
| `no_count` | `INTEGER` | No | Negative count |
| `total` | `INTEGER` | No | Total responses (`0` for silent facilities) |
| `negative_ratio` | `FLOAT` | No | `no_count / total` (`0.0` when `total == 0`) |
| `verdict` | Enum (`clean`, `needs_cleaning`, `insufficient_data`) | No | Window outcome |
| `action` | `VARCHAR(32)` (`none`, `alert`, `escalate`, `insufficient_data`) | No | Action taken during `/evaluate` |
| `reasons` | `JSONB` (list of strings) | No | Human-readable explanation |

**Constraints & Indexes:** `UNIQUE (facility_id, window_start)`, index on `(facility_id, window_start DESC)` and `(verdict, window_start DESC)`.

### 2.7 Maintenance & Cleaning Issues (`maintenance_issues`) — *Written by Government*
| Field | Proposed Type | Nullable? | Why Government Needs It |
| :--- | :--- | :---: | :--- |
| `id` | `UUID` or `VARCHAR` (PK) | No | Primary key |
| `type` | Enum (`cleaning`, `maintenance`) | No | Distinguishes feedback-driven cleaning alerts from maintenance issues |
| `status` | Enum (`open`, `alert_sent`, `acknowledged`, `escalated`, `resolved`, `dismissed`) | No | Lifecycle state |
| `facility_id` | FK → `facilities.id` | No | Target facility |
| `ward` | `VARCHAR(100)` | Yes | Filter on `/issues` |
| `category` | Enum (`FeedbackCategory`) | No | Category of issue |
| `triage_level` | Enum (`urgent`, `high`, `normal`, `unranked`) | No | Government triage classification (not a score) |
| `summary` | `TEXT` | No | Description |
| `responsibility_unverified` | `BOOLEAN` | No | True when facility lacks a verified operator contact |
| `consecutive_negative_windows` | `INTEGER` | No | Tracks persistent negative windows after an alert is created |
| `verification_requested_at` | `TIMESTAMPTZ` | Yes | Timestamp when escalated to physical verification for the Evaluator module |
| `created_at` | `TIMESTAMPTZ` | No | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | No | Last transition/update timestamp |

**Indexes needed:** `(status, type, triage_level)`, `(facility_id, type, status)`, `(ward)`, `(created_at DESC)`.

### 2.8 Issue Audit Entries (`issue_audit_entries`) — *Append-Only, Written by Government*
| Field | Proposed Type | Nullable? | Why Government Needs It |
| :--- | :--- | :---: | :--- |
| `id` | `UUID` or `BIGSERIAL` (PK) | No | Primary key |
| `issue_id` | FK → `maintenance_issues.id` | No | Parent issue |
| `from_status` | Enum (`IssueStatus`) | Yes | `NULL` on initial creation |
| `to_status` | Enum (`IssueStatus`) | No | Target status |
| `actor_id` | `VARCHAR(128)` | No | Authenticated officer ID or `system-evaluate` / `dev-government-user` |
| `note` | `TEXT` | No | Mandatory audit note |
| `timestamp` | `TIMESTAMPTZ` | No | Transition timestamp |

**Indexes needed:** `(issue_id, timestamp ASC)`.

### 2.9 Notification Records (`issue_notifications`) — *Written by Government*
| Field | Proposed Type | Nullable? | Why Government Needs It |
| :--- | :--- | :---: | :--- |
| `id` | `UUID` or `VARCHAR` (PK) | No | Primary key |
| `issue_id` | FK → `maintenance_issues.id` | No | Parent issue |
| `channel` | Enum (`email`, `sms`) | No | `email` in Phase 2 (`sms` reserved) |
| `recipient` | `VARCHAR(254)` | No | Verified operator email |
| `status` | Enum (`created`, `sent`, `failed`, `acknowledged`) | No | Delivery & acknowledgement tracking |
| `created_at` | `TIMESTAMPTZ` | No | Creation time |
| `sent_at` | `TIMESTAMPTZ` | Yes | Delivery time |
| `acknowledged_at` | `TIMESTAMPTZ` | Yes | Operator acknowledgement time |
| `provider_message` | `TEXT` | Yes | Provider status / error detail |
| `payload` | `JSONB` | No | Structured alert payload (references evidence by ID only) |

---

## 3. Open Questions for Shubham

1. **Primary key type:** Should IDs across `facilities`, `inspections`, `citizen_feedback`, and `maintenance_issues` be `UUID` or string slugs (`VARCHAR`)? `domain.py` uses `str` so either converts cleanly.
2. **Official facility score storage vs computation:** Will `app.modules.intelligence` expose `get_facility_score(facility_id: str) -> OfficialScore | dict | float | None` in Python, or also persist a cached score column on `facilities`? `IntelligenceScoreProvider` in `providers/scores.py` is ready to call `intelligence.get_facility_score(facility_id)`.
3. **Citizen feedback sentiment & channel columns:** Please confirm that `citizen_feedback` includes `sentiment` (`positive`/`neutral`/`negative`), `channel` (`app`/`qr`/`web`/`iot`), and `reporter_hash` so repeated-complaint clusters (`>=3` complaints from `>=2` distinct reporters in 14 days) can run in SQL.
4. **Evaluator physical verification handoff:** Escalated cleaning issues set `verification_requested_at` on `maintenance_issues`. Please confirm whether the Evaluator allocation query will read `maintenance_issues WHERE status = 'escalated' AND verification_requested_at IS NOT NULL` directly or via a dedicated table.

