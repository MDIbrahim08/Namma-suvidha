# PROPOSED — AWAITING SHABAZ'S APPROVAL — DO NOT EXECUTE WITHOUT REVIEW

**Document:** Supabase Row Level Security (RLS), Access Matrix & Credential Rotation Proposal  
**Author:** Ibrahim (Backend Integration & Security Audit)  
**Owner / Approver:** **Shabaz** (Authentication, JWT Verification, RBAC, and Database Access Security Owner)  
**Coordinate With:** **Shubham** (Database Schema & SQLAlchemy/Alembic Owner)  
**Status:** `PROPOSED` / `BLOCKED BY APPROVAL` (Zero `ALTER TABLE` or `CREATE POLICY` statements have been executed on the shared Supabase database).

---

## 1. Executive Summary of Critical Security Findings

1. **Row Level Security (RLS) Disabled Across All 7 Public Tables (`CRITICAL`):**
   - Read-only inspection of `pg_tables` and `pg_policies` in the shared Supabase database (`public` schema) revealed `rowsecurity = false` and `0` policies on all 7 tables:
     1. `public.users`
     2. `public.toilets`
     3. `public.citizen_reports`
     4. `public.evaluator_tasks`
     5. `public.evaluator_cooldowns`
     6. `public.inspections`
     7. `public.maintenance_tickets`
   - Because Supabase automatically exposes the `public` schema via PostgREST (`/rest/v1/*`), any caller holding the public `SUPABASE_ANON_KEY` can currently read, insert, update, or delete rows across all 7 tables—including `users.id_document_url`, `users.webauthn_public_key`, `users.wallet_balance`, `users.phone`, and `toilets.authority_contact_email`.
2. **Current Frontend Protection Guardrail (`IMPLEMENTED`):**
   - [`frontend/src/lib/supabase.ts`](file:///d:/alliance-one-hackathon-2026/frontend/src/lib/supabase.ts) intentionally exports `export const supabase = null` and makes **zero** direct PostgREST queries from the browser. Direct Supabase frontend access must remain disabled until Shabaz reviews, approves, and applies the SQL migration in [`20261030_enable_rls_least_privilege.sql`](file:///d:/alliance-one-hackathon-2026/docs/proposals/sql/20261030_enable_rls_least_privilege.sql).
3. **Previously Shared Credentials Treated as Compromised (`ACTION REQUIRED`):**
   - Credentials previously shared in plaintext chat must be treated as compromised and rotated in the Supabase Dashboard before any public or demo deployment. Local `.env` files have been scrubbed of those exposed values.

---

## 2. Architectural Security Principles

1. **Backend-Mediated Privileged Operations:**
   - All privileged writes (creating/updating facilities, assigning evaluator tasks, recording 45-day cooldowns, computing inspection scores/rewards, creating/transitioning maintenance tickets, and sending operator notifications) **must** execute exclusively through the FastAPI backend using verified server-side credentials or service-role/database connections after FastAPI RBAC checks (`require_government_user`, evaluator role checks).
2. **No Broad `authenticated` Policies:**
   - An authenticated citizen account must **never** be able to query other users' profiles, view evaluator identity documents, read operator private phone/email contacts, or modify inspections/tickets.
3. **Column-Level Sensitive Data Protection:**
   - PostgreSQL RLS filters rows (`WHERE`), not columns (`SELECT`). Because `public.toilets` contains `authority_contact_email` and `authority_contact_phone` on the same row as public toilet coordinates/amenities, direct PostgREST `SELECT` on `public.toilets` by `anon` or `authenticated` roles would leak operator contact PII unless restricted via column-level privileges (`REVOKE SELECT (authority_contact_email, authority_contact_phone) ON public.toilets FROM anon, authenticated;`) or served through FastAPI's [`redact_responsible_party()`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/government/domain.py#L46-L67).

---

## 3. Table-by-Table Access Control Specification

### 3.1 `public.users`
- **Sensitive Columns:** `email`, `phone`, `role`, `evaluator_status`, `id_document_url`, `webauthn_credential_id`, `webauthn_public_key`, `wallet_balance`.
- **Who can READ (`SELECT`):**
  - `anon`: **DENY ALL** (no anonymous access to user records).
  - `authenticated`: A user may read **only their own row** (`auth.uid() = id`).
  - `admin` / `government` (via custom JWT claim or backend): May read user metadata only via backend-mediated endpoints; `webauthn_public_key`, `webauthn_credential_id`, and `id_document_url` are restricted to evaluator verification workflows.
- **Who can INSERT (`INSERT`):**
  - Backend-only (or self-registration trigger on `auth.users` where `auth.uid() = id` and `role = 'citizen'`, `wallet_balance = 0`). Users must **never** be able to self-insert `role = 'admin'`, `role = 'government'`, or `evaluator_status = 'approved'`.
- **Who can UPDATE (`UPDATE`):**
  - **Backend-only** for `role`, `evaluator_status`, `wallet_balance`, `webauthn_*`, and `id_document_url`.
  - Authenticated user may update only non-privileged profile fields (`full_name`, `phone`) on their own row (`auth.uid() = id`) if column-level grants are restricted, or preferably **all updates go through FastAPI**.
- **Who can DELETE (`DELETE`):**
  - **Backend-only / Admin-only** (account deletion / DPDP erasure workflow).
- **Records that must remain private:** All rows except the caller's own row; `id_document_url` and `webauthn_*` must never be returned to general API callers.

---

### 3.2 `public.toilets`
- **Sensitive Columns:** `authority_contact_email`, `authority_contact_phone`.
- **Public Columns:** `id`, `name`, `address`, `ward_name`, `location`, `is_free`, `fee_amount`, `toilet_type`, `has_wheelchair_access`, `has_water`, `has_handwash`, `has_gender_separation`, `has_baby_changing`, `has_sanitary_napkin_vending`, `overall_score`, `evaluator_score_avg`, `citizen_score_avg`, `status`, `last_inspected_at`, `created_at`, `updated_at`.
- **Who can READ (`SELECT`):**
  - `anon` & `authenticated`: May read public facility columns **only if** `REVOKE SELECT (authority_contact_email, authority_contact_phone) ON public.toilets FROM anon, authenticated` is applied. Otherwise, all reads go through FastAPI, which enforces [`redact_responsible_party()`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/government/domain.py#L46-L67).
- **Who can INSERT / UPDATE / DELETE:**
  - **Backend-only** (`service_role` / FastAPI admin & government workflows). Citizens and evaluators cannot directly insert, alter, or delete facility master records or scores.

---

### 3.3 `public.citizen_reports`
- **Columns:** `id`, `toilet_id`, `user_id`, `report_type`, `rating`, `comment`, `photo_urls`, `issue_locked`, `issue_no_water`, `issue_dirty`, `issue_accessibility`, `ai_classified_category`, `ai_urgency_level`, `is_verified`, `created_at`.
- **Who can READ (`SELECT`):**
  - `anon`: **DENY direct table read** (prevents scraping `user_id` associations and unmoderated free-text comments/photos). Aggregated or redacted feedback is served via FastAPI.
  - `authenticated`: A logged-in citizen may read **only their own submitted reports** (`auth.uid() = user_id`). Government/Admin read via FastAPI (`/api/v1/government/feedback`).
- **Who can INSERT (`INSERT`):**
  - **Backend-only (Recommended):** Citizen reports (app, QR fallback, and IoT) should be submitted through FastAPI so rate limiting, duplicate protection, abuse moderation, and server-controlled fields (`ai_classified_category`, `ai_urgency_level`, `is_verified = false`) cannot be forged by the client.
  - If authenticated client insert is permitted by Shabaz, enforce `WITH CHECK (user_id = auth.uid() AND is_verified IS FALSE AND ai_classified_category IS NULL AND ai_urgency_level IS NULL)`.
- **Who can UPDATE / DELETE:**
  - **Backend-only** (`service_role` / FastAPI). Citizens cannot retroactively alter verified reports or AI classifications.

---

### 3.4 `public.evaluator_tasks`
- **Columns:** `id`, `toilet_id`, `evaluator_id`, `status`, `photo_challenge_prompt`, `assigned_at`, `due_at`, `completed_at`.
- **Who can READ (`SELECT`):**
  - `anon`: **DENY ALL**.
  - `authenticated`: Only an approved evaluator whose `auth.uid() = evaluator_id` may read their own assigned tasks. (Citizens and other evaluators must not see who is assigned to inspect which toilet or the anti-spoofing `photo_challenge_prompt`.)
- **Who can INSERT / UPDATE / DELETE:**
  - **Backend-only** (`service_role` / FastAPI allocation & inspection submission service). Evaluators cannot self-assign tasks or mark tasks completed without passing backend inspection verification.

---

### 3.5 `public.evaluator_cooldowns`
- **Columns:** `id`, `evaluator_id`, `toilet_id`, `last_inspected_at`, `cooldown_until`.
- **Who can READ (`SELECT`):**
  - `anon`: **DENY ALL**.
  - `authenticated`: Only the evaluator themselves (`auth.uid() = evaluator_id`) may view their own cooldown rows.
- **Who can INSERT / UPDATE / DELETE:**
  - **Backend-only** (`service_role` / FastAPI intelligence & allocation engine owned by Shubham). Evaluators must never be able to shorten or delete their 45-day cooldown records.

---

### 3.6 `public.inspections`
- **Sensitive Columns:** `evaluator_id`, `evaluator_location` (exact GPS point of inspector), `image_hashes`, `biometric_verified`, `reward_amount`, `payment_status`, `ai_confidence_score`, `ai_analysis_notes`.
- **Who can READ (`SELECT`):**
  - `anon`: **DENY direct table read** (citizens receive sanitized inspection summaries via FastAPI without `evaluator_location`, `reward_amount`, or `payment_status`).
  - `authenticated`: Evaluators may read **only their own inspections** (`auth.uid() = evaluator_id`). Government/Admin read via FastAPI.
- **Who can INSERT / UPDATE / DELETE:**
  - **Backend-only** (`service_role` / FastAPI). Inspection submissions must be validated by the backend (geofence check, photo challenge verification, score calculation, and reward computation) before insertion.

---

### 3.7 `public.maintenance_tickets`
- **Sensitive Columns:** `assigned_authority_email`, `assigned_authority_phone`, `authority_response_notes`.
- **Who can READ (`SELECT`):**
  - `anon`: **DENY ALL** (contains operator contact PII and internal escalation notes).
  - `authenticated`: Only users with verified `government` or `admin` role (via backend `/api/v1/government/issues` or strict JWT role check).
- **Who can INSERT / UPDATE / DELETE:**
  - **Backend-only** (`service_role` / FastAPI `IssueService`), which enforces `ALLOWED_ISSUE_TRANSITIONS`, mandatory resolution notes, and append-only audit logging.

---

## 4. Summary Matrix (Least-Privilege Policy Model)

| Table | `anon` (PostgREST) | `authenticated` Citizen | `authenticated` Evaluator | `government` / `admin` | FastAPI Backend (`service_role` / DB Pool) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`users`** | Deny All | `SELECT` own row only (`id = auth.uid()`) | `SELECT` own row only (`id = auth.uid()`) | Read via Backend API | Full (enforces RBAC & PII redaction) |
| **`toilets`** | `SELECT` public cols only (PII cols revoked) | `SELECT` public cols only (PII cols revoked) | `SELECT` public cols only (PII cols revoked) | Read via Backend API (includes operator contact) | Full |
| **`citizen_reports`** | Deny direct table access | `SELECT` own rows (`user_id = auth.uid()`) | `SELECT` own rows | Read via Backend API | Full (rate-limited insert + AI tagging) |
| **`evaluator_tasks`** | Deny All | Deny All | `SELECT` own rows (`evaluator_id = auth.uid()`) | Read/Manage via Backend API | Full (task allocation & anti-cheat) |
| **`evaluator_cooldowns`** | Deny All | Deny All | `SELECT` own rows (`evaluator_id = auth.uid()`) | Read via Backend API | Full (45-day cooldown enforcement) |
| **`inspections`** | Deny direct table access | Deny direct table access (summary via API) | `SELECT` own rows (`evaluator_id = auth.uid()`) | Read via Backend API | Full (score & reward calculation) |
| **`maintenance_tickets`** | Deny All | Deny All | Deny All | Read/Transition via Backend API | Full (state machine & audit trail) |

---

## 5. Reviewable SQL Migration Script

The complete, idempotent, non-destructive SQL migration is prepared at:
- [`docs/proposals/sql/20261030_enable_rls_least_privilege.sql`](file:///d:/alliance-one-hackathon-2026/docs/proposals/sql/20261030_enable_rls_least_privilege.sql)

---

## 6. Approval Checklist for Shabaz

1. **Credential Rotation (Immediate):**
   - Rotate the Supabase database password (`Database -> Settings -> Database password`) and rotate the `service_role` secret key / `anon` key in the Supabase Dashboard.
   - Distribute new credentials out-of-band (never in chat or Git) to local `.env` files only.
2. **Review & Execute RLS Migration:**
   - Review [`docs/proposals/sql/20261030_enable_rls_least_privilege.sql`](file:///d:/alliance-one-hackathon-2026/docs/proposals/sql/20261030_enable_rls_least_privilege.sql).
   - Run the migration in the Supabase SQL Editor during a coordinated window.
   - Run the verification query at the bottom of the script to confirm `rowsecurity = true` on all 7 tables.
3. **JWT Verification Integration (`backend/app/core/security.py`):**
   - Implement `get_current_user` in [`backend/app/core/security.py`](file:///d:/alliance-one-hackathon-2026/backend/app/core/security.py) verifying Supabase JWTs (`Authorization: Bearer <token>`) and populating user `id` and `role` so `require_government_user` in [`dependencies.py`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/government/dependencies.py) transitions seamlessly from `501` to live JWT enforcement.

