# PROPOSED — AWAITING SHABAZ'S APPROVAL — DO NOT EXECUTE WITHOUT REVIEW

**Document:** `docs/EVALUATOR_AUTH_RLS_PROPOSAL.md`  
**Stage:** Stage 2 — Row Level Security (RLS) & Access Control Proposal for Evaluator Authentication  
**Owner / Approver:** **Shabaz** (Authentication, JWT Verification, RBAC & Supabase RLS Owner)  
**Coordinate With:** **Shubham** (Database Schema Owner) & **Ibrahim** (Evaluator & Government Integration)

> **Execution Boundary:** This document and its companion SQL script ([`docs/proposals/sql/20261031_evaluator_auth_rls.sql`](file:///d:/alliance-one-hackathon-2026/docs/proposals/sql/20261031_evaluator_auth_rls.sql)) are **unexecuted proposals**. Zero RLS or grant changes have been executed against the shared Supabase database.

---

## 1. Security Objectives & Threat Boundaries

1. **Zero Self-Approval or Self-Privilege Escalation:**
   - Evaluators and citizens must **never** be able to update `users.role`, `users.evaluator_status`, `users.wallet_balance`, `users.status_updated_by`, or `evaluator_verifications.verification_status` directly via Supabase PostgREST (`anon` or `authenticated` JWTs).
   - All writes to `public.users`, `public.evaluator_verifications`, `public.webauthn_credentials`, `public.webauthn_challenges`, `public.audit_logs`, `public.evaluator_tasks`, `public.evaluator_cooldowns`, and `public.inspections` are **revoked from `anon` and `authenticated`** at the PostgreSQL privilege level and mediated exclusively by the FastAPI backend after server-side RBAC, state-machine, and WebAuthn checks.
2. **Strict Tenant Isolation Between Evaluators:**
   - An authenticated evaluator (`auth.uid()`) can read **only** their own permitted user profile columns, their own verification status metadata (excluding raw storage paths if desired, or scoped strictly to `evaluator_id = auth.uid()`), their own active passkey metadata (excluding raw public key bytes if queried via API), their own assigned tasks (`evaluator_id = auth.uid()`), their own cooldowns, and their own submitted inspections.
   - An evaluator can **never** read another evaluator's profile, government ID verification records, passkeys, tasks, cooldowns, or inspections.
3. **Strict Isolation of Administrative Audit Logs & Challenges:**
   - `public.webauthn_challenges` is **backend-only** (`anon` and `authenticated` have zero `SELECT`/`INSERT`/`UPDATE`/`DELETE` privileges).
   - `public.audit_logs` is **append-only** and readable only by verified `admin` users (or via the FastAPI `/api/v1/admin/audit-logs` endpoint). Evaluators and citizens have zero access to `public.audit_logs`.
4. **Separation of `admin` and `government` Roles:**
   - Evaluator onboarding approval, identity document review (`/api/v1/admin/evaluators/*`), suspension, and reinstatement require the `admin` role (`require_admin`).
   - Government sanitation monitoring (`/api/v1/government/*`) accepts `government` or `admin` (`require_government_user`). A `government` monitoring officer cannot view raw evaluator KYC documents or approve/suspend evaluators unless explicitly granted the `admin` role.

---

## 2. Role & Permission Matrix Across All Evaluator & Core Tables

| Table / Resource | `anon` (Unauthenticated) | `citizen` (`authenticated`) | `evaluator` (`pending` / `rejected` / `suspended`) | `evaluator` (`approved`) | `government` Officer | `admin` | FastAPI Backend (Server Pool / `service_role`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`public.users`** | Deny All | `SELECT` own non-sensitive cols (`id = auth.uid()`) | `SELECT` own non-sensitive cols (`id = auth.uid()`) | `SELECT` own non-sensitive cols (`id = auth.uid()`) | Own row (`id = auth.uid()`) | Read/Manage via FastAPI Admin API | Full (enforces lifecycle transitions) |
| **`public.evaluator_verifications`** | Deny All | Deny All | `SELECT` own status metadata (`evaluator_id = auth.uid()`) | `SELECT` own status metadata (`evaluator_id = auth.uid()`) | Deny All | Review & Approve/Reject via FastAPI Admin API | Full |
| **`public.webauthn_credentials`** | Deny All | Deny All | `SELECT` own passkey metadata (`user_id = auth.uid()`) | `SELECT` own passkey metadata (`user_id = auth.uid()`) | Deny All | View metadata / revoke via FastAPI | Full (verifies cryptographic signatures & counters) |
| **`public.webauthn_challenges`** | **Deny All** | **Deny All** | **Deny All (Backend-Only)** | **Deny All (Backend-Only)** | **Deny All** | **Deny All (Backend-Only)** | Full (creates & atomically consumes challenges) |
| **`public.audit_logs`** | **Deny All** | **Deny All** | **Deny All** | **Deny All** | Deny (except issue audit in Gov API) | Read via `/api/v1/admin/audit-logs` | `INSERT` + `SELECT` only (`UPDATE`/`DELETE` blocked by trigger) |
| **`public.evaluator_tasks`** | Deny All | Deny All | Deny active task execution | `SELECT` own tasks (`evaluator_id = auth.uid()`) | Summary via Gov API | Read/Allocate via FastAPI | Full (enforces 45-day cooldown & approval check) |
| **`public.evaluator_cooldowns`** | Deny All | Deny All | `SELECT` own (`evaluator_id = auth.uid()`) | `SELECT` own (`evaluator_id = auth.uid()`) | Deny All | Read via FastAPI | Full (Shubham's 45-day cooldown engine) |
| **`public.inspections`** | Deny direct table read | Deny direct table read (sanitized summary via API) | `SELECT` own historical rows (`evaluator_id = auth.uid()`); **cannot submit** | `SELECT` own rows; submit via FastAPI + WebAuthn assertion | Read summary via Gov API | Full review via FastAPI | Full |
| **Storage: `storage.objects` (`bucket_id = 'evaluator-ids'`)** | **Deny All** | **Deny All** | **Deny direct PostgREST access** (upload via FastAPI or strict path policy) | **Deny direct PostgREST access** | **Deny All** | **Short-lived (60s) signed URL via FastAPI Admin endpoint** | Generates signed upload/preview URLs & runs retention purge |

---

## 3. Detailed Table-by-Table RLS & Column Privilege Design

### 3.1 `public.users`
- **RLS Enabled:** `ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;`
- **Table-Level Write Revocation:** `REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.users FROM anon, authenticated;`
  - *Why:* Prevents any user from calling PostgREST `PATCH /rest/v1/users?id=eq.<uid>` with `{"role": "admin"}` or `{"evaluator_status": "approved"}` or `{"wallet_balance": 99999}`.
- **Column-Level `SELECT` Grant for `authenticated`:**
  - Granted columns: `id`, `full_name`, `email`, `phone`, `role`, `evaluator_status`, `operating_area`, `preferred_language`, `application_reference`, `email_verified_at`, `status_updated_at`, `status_reason`, `wallet_balance`, `created_at`, `updated_at`.
  - **Revoked columns (`anon` & `authenticated`):** `id_document_url`, `webauthn_credential_id`, `webauthn_public_key`, `status_updated_by`.
- **Row Policy (`users_select_own`):**
  ```sql
  CREATE POLICY users_select_own
      ON public.users
      FOR SELECT
      TO authenticated
      USING (auth.uid() = id);
  ```

### 3.2 `public.evaluator_verifications`
- **RLS Enabled:** `ALTER TABLE public.evaluator_verifications ENABLE ROW LEVEL SECURITY;`
- **Write Revocation:** `REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.evaluator_verifications FROM anon, authenticated;`
- **Column-Level `SELECT` Grant for `authenticated`:**
  - Granted columns: `id`, `evaluator_id`, `application_reference`, `document_type`, `verification_status`, `reviewed_at`, `rejection_reason`, `created_at`, `updated_at`.
  - **Revoked columns (`anon` & `authenticated`):** `document_storage_bucket`, `document_storage_path`, `sha256_checksum`, `reviewed_by`, `retention_expires_at`, `purged_at`.
- **Row Policy (`evaluator_verifications_select_own`):**
  ```sql
  CREATE POLICY evaluator_verifications_select_own
      ON public.evaluator_verifications
      FOR SELECT
      TO authenticated
      USING (auth.uid() = evaluator_id);
  ```

### 3.3 `public.webauthn_credentials`
- **RLS Enabled:** `ALTER TABLE public.webauthn_credentials ENABLE ROW LEVEL SECURITY;`
- **Write Revocation:** `REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.webauthn_credentials FROM anon, authenticated;`
- **Column-Level `SELECT` Grant for `authenticated`:**
  - Granted columns: `id`, `user_id`, `credential_id`, `device_name`, `transports`, `backed_up`, `created_at`, `last_used_at`, `revoked_at`.
  - **Revoked columns (`anon` & `authenticated`):** `public_key`, `sign_count`, `aaguid`, `revoked_by`, `revoke_reason`.
- **Row Policy (`webauthn_credentials_select_own`):**
  ```sql
  CREATE POLICY webauthn_credentials_select_own
      ON public.webauthn_credentials
      FOR SELECT
      TO authenticated
      USING (auth.uid() = user_id);
  ```

### 3.4 `public.webauthn_challenges`
- **RLS Enabled:** `ALTER TABLE public.webauthn_challenges ENABLE ROW LEVEL SECURITY;`
- **All Client Privileges Revoked:** `REVOKE ALL ON public.webauthn_challenges FROM anon, authenticated;`
- **Zero Client Policies:** No `CREATE POLICY` is added for `anon` or `authenticated`, so PostgREST denies all client access by default. Challenges are generated, verified, and consumed exclusively by the FastAPI backend.

### 3.5 `public.audit_logs`
- **RLS Enabled:** `ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;`
- **All Client Privileges Revoked:** `REVOKE ALL ON public.audit_logs FROM anon, authenticated;`
- **Append-Only Trigger:** `trg_audit_logs_immutable` blocks `UPDATE` and `DELETE` on `public.audit_logs`.
- **Admin Access:** Served exclusively through the FastAPI endpoint `GET /api/v1/admin/audit-logs` guarded by `require_admin`.

### 3.6 `public.evaluator_tasks`, `public.evaluator_cooldowns`, and `public.inspections`
- **RLS Enabled & Writes Revoked** from `anon` and `authenticated`.
- **`evaluator_tasks_select_own_approved`:**
  ```sql
  CREATE POLICY evaluator_tasks_select_own_approved
      ON public.evaluator_tasks
      FOR SELECT
      TO authenticated
      USING (
          auth.uid() = evaluator_id
          AND EXISTS (
              SELECT 1 FROM public.users u
              WHERE u.id = auth.uid()
                AND u.role = 'evaluator'
                AND u.evaluator_status = 'approved'
          )
      );
  ```
  *(Note: If an evaluator is `pending`, `rejected`, or `suspended`, even direct PostgREST `SELECT` on `evaluator_tasks` returns 0 rows.)*

---

## 4. Backend FastAPI Authorization Guards & Non-Intrusive Integration Interface (Coordination with Shabaz)

### 4.1 Protecting `backend/app/core/security.py` Until Shabaz Approves
- [`backend/app/core/security.py`](file:///d:/alliance-one-hackathon-2026/backend/app/core/security.py) is owned by **Shabaz** and must **not** be modified without his explicit approval.
- To allow Stage 3 development and testing without touching `security.py`, the Evaluator module will use an **Auth Provider Adapter (`EvaluatorAuthProvider`)** that follows the exact same pattern as [`require_government_user`](file:///d:/alliance-one-hackathon-2026/backend/app/modules/government/dependencies.py#L103-L141):
  1. First checks `request.app.dependency_overrides.get(get_current_user)` so tests can inject verified mock principals cleanly.
  2. If `get_current_user` is not overridden and `Authorization: Bearer <token>` is present, verifies the Supabase JWT using `SupabaseJwtVerifier` (which validates signature, `iss`, `aud`, `exp`, `sub`, and supports both `HS256` with `SUPABASE_JWT_SECRET` and asymmetric `ES256`/`RS256` via Supabase's JWKS endpoint `https://<project_ref>.supabase.co/auth/v1/.well-known/jwks.json`).
  3. **Never accepts unsigned (`alg: "none"`), malformed, expired, or unverified tokens.**
  4. Preserves existing Government module test behavior 100% (unauthenticated calls to `/api/v1/government/*` when `SUPABASE_JWT_SECRET` is unset still delegate to Shabaz's `get_current_user()` stub and return `501`, or `401`/`403` when overridden).

### 4.2 Five Composable Server-Side Guards
1. **`get_verified_principal(request) -> AuthenticatedPrincipal`**:
   - Extracts `Authorization: Bearer <jwt>`.
   - Validates signature (`HS256` via `SUPABASE_JWT_SECRET` or `ES256`/`RS256` via JWKS discovery), `exp`, `iat`, `iss` (`https://<project_ref>.supabase.co/auth/v1`), and `aud` (`authenticated`).
   - Resolves `sub` (`user_id`), `email`, and `email_confirmed_at`.
2. **`require_authenticated_user(principal = Depends(get_verified_principal))`**:
   - Ensures valid non-expired token and verified email (`email_confirmed_at` present).
3. **`require_evaluator(user = Depends(require_authenticated_user))`**:
   - Loads the user's authoritative row from `EvaluatorRepository` / `public.users` (never trusting client-supplied role claims alone) and verifies `user.role == 'evaluator'`.
   - Permitted on onboarding endpoints (`/api/v1/evaluators/me`, `/status`, `/documents`, `/passkeys/register/*`) regardless of whether `evaluator_status` is `pending`.
4. **`require_approved_evaluator(user = Depends(require_evaluator))`**:
   - Verifies `user.evaluator_status == 'approved'` **and** at least one active (non-revoked) WebAuthn credential exists.
   - Immediately rejects `pending`, `rejected`, or `suspended` evaluators with `HTTP 403 Forbidden` (`code="evaluator_not_approved"`) and writes a `security.privileged_access_denied` audit log entry.
5. **`require_admin(user = Depends(require_authenticated_user))`**:
   - Verifies from the authoritative backend record that `user.role == 'admin'`.
   - Protects all `/api/v1/admin/*` endpoints.

---

## 5. Audit Log Immutability & Privileged Database Access Hardening

1. **Ordinary Application Connections Cannot Mutate Audit Logs:**
   - Even if an application query runs over the backend database pool, `public.audit_logs` is protected by a PostgreSQL trigger (`trg_audit_logs_immutable` executing `BEFORE UPDATE OR DELETE ON public.audit_logs`) that unconditionally raises an exception:
     `public.audit_logs is append-only; UPDATE and DELETE are forbidden.`
   - Furthermore, in [`20261031_evaluator_auth_rls.sql`](file:///d:/alliance-one-hackathon-2026/docs/proposals/sql/20261031_evaluator_auth_rls.sql), `REVOKE ALL ON public.audit_logs FROM anon, authenticated;` and `REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM service_role;` ensure that even `service_role` can only `INSERT` and `SELECT` on `public.audit_logs`.
2. **Storage Object Isolation (`storage.objects`):**
   - Explicit `CREATE POLICY ... AS RESTRICTIVE` deny policies on `storage.objects` for `bucket_id IN ('evaluator-ids', 'inspection-evidence')` ensure that `anon` and `authenticated` PostgREST/Storage clients cannot read, list, overwrite, or delete private identity documents or unreviewed inspection evidence directly.

