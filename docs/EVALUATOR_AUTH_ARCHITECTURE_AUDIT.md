# Namma Suvidha — Stage 1: Evaluator Authentication, Management & Inspection Access Architecture Audit

**Document:** `docs/EVALUATOR_AUTH_ARCHITECTURE_AUDIT.md`  
**Stage:** Stage 1 — Architecture and Security Audit (Read-Only Inspection)  
**Authors / Owners:**
- **Shabaz:** Authentication, JWT verification (`backend/app/core/security.py`), RBAC, security middleware, and Supabase RLS.
- **Shubham:** Database schema, SQLAlchemy ORM models (`backend/app/db/base.py`), Alembic migrations, 45-day evaluator cooldown, and weighted inspection scoring (`backend/app/modules/intelligence/`).
- **Ibrahim:** Evaluator workflow integration, Government backend (`backend/app/modules/government/`), Discovery (`backend/app/modules/discovery/`), OpenRouter Voice Pipeline (`backend/app/modules/openrouter/`), and cross-module orchestration.
- **Gaurish:** Frontend UI/UX (`frontend/src/`).

> **Stage 1 Compliance Note:** Zero application source files, SQL tables, Supabase settings, authentication stubs, or database models were modified in this stage.

---

## 1. Executive Summary

This audit inspects the complete Namma Suvidha repository and live Supabase database structure to prepare the **Gig Worker Authentication, Evaluator Management & Inspection Access System**.

Key findings:
1. **Canonical User & Evaluator Tables Already Exist in Shared Supabase:** The shared Supabase database (`public` schema) already contains `public.users`, `public.evaluator_tasks`, `public.evaluator_cooldowns`, and `public.inspections`. Creating a parallel `public.profiles` table would violate the single-source-of-truth rule; instead, we must extend or complement `public.users` in coordination with Shubham and Shabaz.
2. **Existing WebAuthn Columns in `public.users` Are Single-Device & Lack Counter/Challenge State:** `public.users` currently has inline `webauthn_credential_id` (`text`) and `webauthn_public_key` (`text`) columns, which lack `sign_count`, `transports`, `device_name`, `revoked_at`, multi-device support, and a server-side challenge store (`webauthn_challenges`).
3. **Authentication & Evaluator Modules Are Currently Phase 0 Stubs:** [`backend/app/core/security.py`](file:///d:/alliance-one-hackathon-2026/backend/app/core/security.py), [`backend/app/api/v1/evaluator.py`](file:///d:/alliance-one-hackathon-2026/backend/app/api/v1/evaluator.py), [`backend/app/modules/evaluator/__init__.py`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/evaluator/__init__.py), [`frontend/src/lib/supabase.ts`](file:///d:/alliance-one-hackathon-2026/frontend/src/lib/supabase.ts), and [`frontend/src/features/evaluator/pages/EvaluatorHome.tsx`](file:///d:/alliance-one-hackathon-2026/frontend/src/features/evaluator/pages/EvaluatorHome.tsx) are all Phase 0 placeholders awaiting implementation.

---

## 2. Detailed Audit of Existing Components

### 2.1 Existing Authentication Implementation (`NOT IMPLEMENTED` — Stub Only)

- **Backend ([`backend/app/core/security.py`](file:///d:/alliance-one-hackathon-2026/backend/app/core/security.py)):**
  - Owned by **Shabaz**.
  - Currently contains a 19-line stub where `get_current_user()` unconditionally raises `HTTP 501 Not Implemented` (`"Authentication not implemented — owned by Shabaz"`).
  - No JWT decoding library (`PyJWT` / `python-jose` / `cryptography`) or WebAuthn library (`py_webauthn`) is currently listed in [`backend/requirements.txt`](file:///d:/alliance-one-hackathon-2026/backend/requirements.txt).
- **Government Module Role Adaptation ([`backend/app/modules/government/dependencies.py`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/government/dependencies.py)):**
  - Owned by **Ibrahim**.
  - Implements `extract_roles(principal)`, `extract_actor_id(principal)`, and `require_government_user(request, response)`, which delegates token verification to `get_current_user` from [`security.py`](file:///d:/alliance-one-hackathon-2026/backend/app/core/security.py) and enforces `government` or `admin` role (`HTTP 403` when an authenticated `citizen` or `evaluator` calls `/api/v1/government/*`).
- **Frontend ([`frontend/src/lib/supabase.ts`](file:///d:/alliance-one-hackathon-2026/frontend/src/lib/supabase.ts)):**
  - Owned by **Shabaz**.
  - `@supabase/supabase-js` (`^2.45.0`) is installed in [`frontend/package.json`](file:///d:/alliance-one-hackathon-2026/frontend/package.json), but [`supabase.ts`](file:///d:/alliance-one-hackathon-2026/frontend/src/lib/supabase.ts) currently exports `export const supabase = null`.
  - [`frontend/src/lib/api/client.ts`](file:///d:/alliance-one-hackathon-2026/frontend/src/lib/api/client.ts) has a `TODO (Phase 1 - Shabaz)` comment to attach `Authorization: Bearer <access_token>` from `supabase.auth.getSession()`.

---

### 2.2 Existing User / Profile & Evaluator Tables in Shared Supabase (`LIVE VERIFIED`)

Read-only inspection of the shared Supabase PostgreSQL database (`public` schema) identified 7 existing tables. Four of these directly relate to users, evaluators, tasks, and inspections:

#### A. `public.users` (Canonical User & Evaluator Profile Table)
| Column | Data Type | Nullable | Notes vs. Target Evaluator Requirements |
| :--- | :--- | :---: | :--- |
| `id` | `uuid` (PK) | `NO` | Canonical user/evaluator UUID |
| `full_name` | `character varying` | `NO` | Matches requirement |
| `email` | `character varying` | `NO` | Matches requirement |
| `phone` | `character varying` | `YES` | Named `phone` (prompt suggests `phone_number`; **must reuse `phone`** to avoid duplicate columns) |
| `role` | `character varying` | `NO` | Stores role (`citizen`, `evaluator`, `government`, `admin`) |
| `evaluator_status` | `character varying` | `YES` | Stores lifecycle status (`pending`, `approved`, `rejected`, `suspended`) |
| `id_document_url` | `text` | `YES` | Stores document reference (must store private storage path `evaluator-ids/{user_id}/...`, never a permanent public URL) |
| `webauthn_credential_id` | `text` | `YES` | Legacy single-credential column (insufficient for multi-device, `sign_count`, and revocation) |
| `webauthn_public_key` | `text` | `YES` | Legacy single-key column |
| `wallet_balance` | `numeric` | `NO` | Evaluator reward balance |
| `created_at` | `timestamp with time zone` | `NO` | Profile creation timestamp |
| `updated_at` | `timestamp with time zone` | `NO` | Last update timestamp |

> **Missing on `public.users`:** `operating_area` (`varchar`), `preferred_language` (`varchar`, optional), and separate verification metadata (`evaluator_verifications` table) so sensitive document paths and rejection reasons are not exposed in ordinary profile queries.

#### B. `public.evaluator_tasks` (Existing Task Assignment Table)
| Column | Data Type | Nullable |
| :--- | :--- | :---: |
| `id` | `uuid` (PK) | `NO` |
| `toilet_id` | `uuid` (FK → `toilets.id`) | `NO` |
| `evaluator_id` | `uuid` (FK → `users.id`) | `NO` |
| `status` | `character varying` | `NO` |
| `photo_challenge_prompt` | `text` | `NO` |
| `assigned_at` | `timestamp with time zone` | `NO` |
| `due_at` | `timestamp with time zone` | `NO` |
| `completed_at` | `timestamp with time zone` | `YES` |

#### C. `public.evaluator_cooldowns` (Existing 45-Day Cooldown Table)
| Column | Data Type | Nullable |
| :--- | :--- | :---: |
| `id` | `uuid` (PK) | `NO` |
| `evaluator_id` | `uuid` (FK → `users.id`) | `NO` |
| `toilet_id` | `uuid` (FK → `toilets.id`) | `NO` |
| `last_inspected_at` | `timestamp with time zone` | `NO` |
| `cooldown_until` | `timestamp with time zone` | `NO` |

#### D. `public.inspections` (Existing Inspection Submission Table)
| Column | Data Type | Nullable |
| :--- | :--- | :---: |
| `id` | `uuid` (PK) | `NO` |
| `task_id` | `uuid` (FK → `evaluator_tasks.id`) | `YES` |
| `toilet_id` | `uuid` (FK → `toilets.id`) | `NO` |
| `evaluator_id` | `uuid` (FK → `users.id`) | `NO` |
| `cleanliness_score`, `lighting_safety_score` | `smallint` | `NO` |
| `water_available`, `toilet_functional`, `ramp_accessible`, `grab_rails_present`, `handwash_available` | `boolean` | `NO` |
| `calculated_score` | `numeric` | `NO` |
| `photo_urls`, `image_hashes` | `ARRAY` | `NO` / `YES` |
| `evaluator_location` | `USER-DEFINED` (PostGIS) | `NO` |
| `distance_from_toilet_meters` | `numeric` | `YES` |
| `biometric_verified` | `boolean` | `NO` |
| `ai_verification_status`, `verification_status`, `payment_status` | `character varying` | `NO` |
| `ai_confidence_score`, `reward_amount` | `numeric` | `YES` / `NO` |
| `ai_analysis_notes`, `inspector_notes` | `text` | `YES` |
| `submitted_at` | `timestamp with time zone` | `NO` |

---

### 2.3 Existing SQLAlchemy ORM & Alembic State (`NOT IMPLEMENTED` in Python)

- [`backend/app/db/base.py`](file:///d:/alliance-one-hackathon-2026/backend/app/db/base.py) (owned by **Shubham**) defines `Base = declarative_base()` with zero ORM classes registered yet.
- [`backend/alembic/env.py`](file:///d:/alliance-one-hackathon-2026/backend/alembic/env.py) is configured to read `DATABASE_URL` from [`app/core/config.py`](file:///d:/alliance-one-hackathon-2026/backend/app/core/config.py), and `backend/alembic/versions/` currently contains no migration files.

---

### 2.4 Existing RLS Policies (`BLOCKED BY APPROVAL`)

- Live inspection confirmed `rowsecurity = False` and `0` policies on all 7 `public` tables in Supabase.
- Baseline RLS policies for the 7 existing tables were proposed in [`docs/proposals/SUPABASE_RLS_AND_SECURITY_PROPOSAL.md`](file:///d:/alliance-one-hackathon-2026/docs/proposals/SUPABASE_RLS_AND_SECURITY_PROPOSAL.md) and [`docs/proposals/sql/20261030_enable_rls_least_privilege.sql`](file:///d:/alliance-one-hackathon-2026/docs/proposals/sql/20261030_enable_rls_least_privilege.sql), awaiting Shabaz's review and execution.
- Stage 2 of this Evaluator Auth module will extend that RLS proposal to cover the new evaluator verification, WebAuthn credentials/challenges, audit logs, and private `evaluator-ids` Storage bucket policies.

---

### 2.5 Existing Storage Buckets (`NOT CONFIGURED` in Codebase)

- There is currently no `backend/app/core/supabase_client.py` or Storage upload/signed-URL service in the backend.
- The private bucket `evaluator-ids` (for government ID cards under `evaluator-ids/{user_id}/...`) and private bucket `inspection-evidence` (for unreviewed inspection photos) must be provisioned in Supabase Storage with strict RLS policies on `storage.objects`.

---

### 2.6 Existing Task Allocation & Inspection Submission Systems

- **Database Tables:** `public.evaluator_tasks`, `public.evaluator_cooldowns`, and `public.inspections` exist in Supabase.
- **Backend Code:**
  - [`backend/app/modules/intelligence/__init__.py`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/intelligence/__init__.py) (owned by **Shubham**) is currently an empty placeholder module (`"""AI and scoring logic. OWNER: Shubham. Empty in Phase 0."""`).
  - [`backend/app/modules/evaluator/__init__.py`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/evaluator/__init__.py) and [`backend/app/api/v1/evaluator.py`](file:///d:/alliance-one-hackathon-2026/backend/app/api/v1/evaluator.py) (owned by **Ibrahim + Shabaz**) are empty Phase 0 stubs.
  - [`backend/app/modules/government/interfaces.py`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/government/interfaces.py) defines read-only `InspectionSummary` and `FacilityScoreProvider` protocols consumed by the Government Monitoring module.

---

### 2.7 Existing Audit Logging (`PARTIALLY IMPLEMENTED` in Government Module Only)

- **Government Issue Audit Log:** [`backend/app/modules/government/domain.py`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/government/domain.py) defines `IssueAuditEntry` (in-memory append-only audit log for maintenance issue transitions).
- **System-Wide / Evaluator Audit Log:** There is currently no `public.audit_logs` table in Supabase and no `backend/app/core/audit.py` service for recording evaluator registration, ID document uploads, passkey registration/revocation, admin approvals/rejections/suspensions/reinstatements, task assignments, or inspection submissions.

---

## 3. Ownership Conflicts & Architectural Alignment Decisions

| Conflict / Ambiguity | Existing Codebase / DB Reality | Proposed Non-Breaking Resolution | Owner Approval Needed |
| :--- | :--- | :--- | :--- |
| **1. `public.profiles` vs. `public.users`** | `public.users` **already exists** in Supabase with `id`, `full_name`, `email`, `phone`, `role`, `evaluator_status`, `id_document_url`, `webauthn_credential_id`, `webauthn_public_key`, `wallet_balance`, `created_at`, `updated_at`. | **Do NOT create a duplicate `public.profiles` table.** Reuse `public.users` as the canonical user/evaluator table, adding only `operating_area` (`varchar`) and `preferred_language` (`varchar`) via a reviewable `ALTER TABLE` migration, and move sensitive document lifecycle metadata into `public.evaluator_verifications`. | **Shubham** (DB Schema) & **Shabaz** (Auth/RLS) |
| **2. Inline `users.webauthn_*` Columns vs. Multi-Device Passkeys (`public.webauthn_credentials`)** | `public.users` has two text columns (`webauthn_credential_id`, `webauthn_public_key`), which cannot store `sign_count`, `transports`, `device_name`, `last_used_at`, `revoked_at`, or multiple passkeys per user, nor short-lived WebAuthn challenges. | Propose `public.webauthn_credentials` (for public keys, sign counters, transports, revocation) and `public.webauthn_challenges` (for single-use, short-lived, operation-bound challenges) while keeping `users.webauthn_credential_id` nullable/deprecated for backward compatibility. | **Shubham** & **Shabaz** |
| **3. Module Naming (`app/modules/evaluator` vs. `app/modules/evaluators`) and Route Prefix (`/api/v1/evaluator` vs. `/api/v1/evaluators`)** | Phase 0 created [`backend/app/modules/evaluator/`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/evaluator/__init__.py) and [`backend/app/api/v1/evaluator.py`](file:///d:/alliance-one-hackathon-2026/backend/app/api/v1/evaluator.py) (`prefix="/evaluator"`), whereas Section 9 specifies `/api/v1/evaluators/*` and `/api/v1/admin/*`. | Implement the domain inside `backend/app/modules/evaluator/` (preserving the Phase 0 package) and mount routes at `/api/v1/evaluators/*` (with `/api/v1/evaluator/*` alias support) and `/api/v1/admin/*`. | **Ibrahim** & **Shabaz** |
| **4. `backend/app/core/security.py` Ownership** | [`backend/app/core/security.py`](file:///d:/alliance-one-hackathon-2026/backend/app/core/security.py) is owned by **Shabaz**. | Do not overwrite [`security.py`](file:///d:/alliance-one-hackathon-2026/backend/app/core/security.py) without approval. Prepare the JWT verification and role-guard contract (`get_current_user`, `require_authenticated_user`, `require_admin`, `require_evaluator`, `require_approved_evaluator`) in Stage 2/3 so it plugs cleanly into `security.py` upon approval. | **Shabaz** |
| **5. Frontend Directory Layout (`src/features/evaluator/` vs. `src/pages/evaluator/`)** | Existing frontend uses feature-first folders (`src/features/citizen/`, `src/features/evaluator/`, `src/features/government/`) routed from [`src/app/router.tsx`](file:///d:/alliance-one-hackathon-2026/frontend/src/app/router.tsx). [`LandingPage.test.tsx`](file:///d:/alliance-one-hackathon-2026/frontend/src/pages/LandingPage.test.tsx) asserts that `/evaluator` renders an `<h1>Evaluator</h1>` heading. | Place Evaluator & Admin UI components under `src/features/evaluator/` (or re-export from `src/pages/evaluator/` and `src/pages/admin/`) while preserving `/evaluator` and its `<h1>Evaluator</h1>` heading so all Phase 0 tests continue to pass. | **Gaurish** & **Ibrahim** |

---

## 4. Component Status Summary Matrix

| Component / Capability | Current Status | Notes |
| :--- | :--- | :--- |
| **Supabase `public.users`, `evaluator_tasks`, `evaluator_cooldowns`, `inspections` Tables** | `LIVE VERIFIED` | Present in Supabase PostgreSQL 17.11; RLS currently disabled (`rowsecurity = false`). |
| **`public.evaluator_verifications`, `public.webauthn_credentials`, `public.webauthn_challenges`, `public.audit_logs` Tables** | `NOT IMPLEMENTED` | To be proposed in Stage 2 migration script for Shubham & Shabaz's approval. |
| **Private Storage Bucket `evaluator-ids` & Signed URL Workflow** | `NOT IMPLEMENTED` | To be proposed in Stage 2 and implemented in Stage 3. |
| **Supabase JWT Verification (`get_current_user`) & Role Guards (`require_admin`, `require_approved_evaluator`)** | `NOT IMPLEMENTED` | Stub in [`backend/app/core/security.py`](file:///d:/alliance-one-hackathon-2026/backend/app/core/security.py) raises `501`; owned by Shabaz. |
| **Real WebAuthn / FIDO2 Challenge-Response Registration & Assertion Verification** | `NOT IMPLEMENTED` | To be designed in Stage 2 and implemented in Stage 4. |
| **Evaluator Lifecycle State Machine (`pending`, `approved`, `rejected`, `suspended`) & Audit Logging** | `NOT IMPLEMENTED` | To be implemented in Stage 3. |
| **Evaluator Task Allocation & Inspection Submission Guard with WebAuthn + Idempotency** | `NOT IMPLEMENTED` | DB tables exist; backend service integration to be implemented in Stage 7. |
| **React Evaluator Onboarding, Dashboard, Passkey UI & Admin Review Panel** | `NOT IMPLEMENTED` | Placeholder in [`EvaluatorHome.tsx`](file:///d:/alliance-one-hackathon-2026/frontend/src/features/evaluator/pages/EvaluatorHome.tsx); to be implemented in Stages 5–6. |
| **Existing Phase 0, Citizen Discovery, OpenRouter Voice Pipeline, & Government Monitoring Modules** | `IMPLEMENTED / TESTED` | `148 passed, 2 skipped` backend tests; `11 passed` frontend tests. |

