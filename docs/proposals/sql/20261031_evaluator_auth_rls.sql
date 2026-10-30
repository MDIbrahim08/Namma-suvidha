-- =============================================================================
-- NAMMA SUVIDHA — EVALUATOR AUTHENTICATION & STORAGE RLS PROPOSAL
-- =============================================================================
-- FILE: docs/proposals/sql/20261031_evaluator_auth_rls.sql
-- STATUS: PROPOSED — AWAITING SHABAZ'S APPROVAL
-- DO NOT EXECUTE AUTOMATICALLY WITHOUT EXPLICIT TEAM APPROVAL.
--
-- Prerequisite:
--   - `20261030_enable_rls_least_privilege.sql` (base 7 tables)
--   - `20261031_evaluator_auth_schema.sql` (evaluator auth tables & columns)
--
-- Security Guarantees:
--   1. Enables RLS on `evaluator_verifications`, `webauthn_credentials`,
--      `webauthn_challenges`, and `audit_logs` (plus existing tables).
--   2. Revokes all direct client (`anon`, `authenticated`) write privileges
--      so evaluators cannot self-approve, escalate roles, alter cooldowns,
--      or forge audit records.
--   3. Restricts column-level SELECT on `users`, `evaluator_verifications`,
--      and `webauthn_credentials` so raw storage paths, public key bytes,
--      and reviewer IDs are never exposed via PostgREST.
--   4. Locks down `storage.objects` for `evaluator-ids` and `inspection-evidence`
--      so all uploads and 60-second admin signed URLs are mediated by FastAPI.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- STEP 1: Enable Row Level Security on all new & existing Evaluator tables
-- -----------------------------------------------------------------------------
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluator_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webauthn_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webauthn_challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluator_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluator_cooldowns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inspections ENABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- STEP 2: Revoke direct client writes (`anon` & `authenticated`)
-- All mutations must be mediated by the FastAPI backend after RBAC & WebAuthn
-- verification.
-- -----------------------------------------------------------------------------
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.users FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.evaluator_verifications FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.webauthn_credentials FROM anon, authenticated;
REVOKE ALL ON public.webauthn_challenges FROM anon, authenticated;
REVOKE ALL ON public.audit_logs FROM anon, authenticated;
REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM service_role;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.evaluator_tasks FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.evaluator_cooldowns FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.inspections FROM anon, authenticated;

-- -----------------------------------------------------------------------------
-- STEP 3: Column-level SELECT grants for `authenticated`
-- -----------------------------------------------------------------------------

-- 3A. `public.users`: Expose only safe profile & status fields to the owner
REVOKE SELECT ON public.users FROM anon, authenticated;
GRANT SELECT (
    id,
    full_name,
    email,
    phone,
    role,
    evaluator_status,
    operating_area,
    preferred_language,
    application_reference,
    email_verified_at,
    status_updated_at,
    status_reason,
    wallet_balance,
    created_at,
    updated_at
) ON public.users TO authenticated;

-- 3B. `public.evaluator_verifications`: Exclude `document_storage_path`,
-- `document_storage_bucket`, `sha256_checksum`, and `reviewed_by`
REVOKE SELECT ON public.evaluator_verifications FROM anon, authenticated;
GRANT SELECT (
    id,
    evaluator_id,
    application_reference,
    document_type,
    verification_status,
    reviewed_at,
    rejection_reason,
    created_at,
    updated_at
) ON public.evaluator_verifications TO authenticated;

-- 3C. `public.webauthn_credentials`: Exclude raw `public_key`, `sign_count`,
-- `aaguid`, and `revoked_by`
REVOKE SELECT ON public.webauthn_credentials FROM anon, authenticated;
GRANT SELECT (
    id,
    user_id,
    credential_id,
    device_name,
    transports,
    backed_up,
    user_verified_on_register,
    created_at,
    last_used_at,
    revoked_at
) ON public.webauthn_credentials TO authenticated;

-- -----------------------------------------------------------------------------
-- STEP 4: Row-Level SELECT Policies (Strict Owner Isolation)
-- -----------------------------------------------------------------------------

-- 1. `public.users`: Authenticated user can read only their own row
DROP POLICY IF EXISTS users_select_own ON public.users;
CREATE POLICY users_select_own
    ON public.users
    FOR SELECT
    TO authenticated
    USING (auth.uid() = id);

-- 2. `public.evaluator_verifications`: Evaluator can read only their own status
DROP POLICY IF EXISTS evaluator_verifications_select_own ON public.evaluator_verifications;
CREATE POLICY evaluator_verifications_select_own
    ON public.evaluator_verifications
    FOR SELECT
    TO authenticated
    USING (auth.uid() = evaluator_id);

-- 3. `public.webauthn_credentials`: User can read only their own registered devices
DROP POLICY IF EXISTS webauthn_credentials_select_own ON public.webauthn_credentials;
CREATE POLICY webauthn_credentials_select_own
    ON public.webauthn_credentials
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- 4. `public.webauthn_challenges`: Zero client policies (Backend-only access)
DROP POLICY IF EXISTS webauthn_challenges_deny_all ON public.webauthn_challenges;

-- 5. `public.audit_logs`: Zero client policies (Backend & Admin API access only)
DROP POLICY IF EXISTS audit_logs_deny_all ON public.audit_logs;

-- 6. `public.evaluator_tasks`: Only an APPROVED evaluator can read their own assigned tasks
DROP POLICY IF EXISTS evaluator_tasks_select_own ON public.evaluator_tasks;
DROP POLICY IF EXISTS evaluator_tasks_select_own_approved ON public.evaluator_tasks;
CREATE POLICY evaluator_tasks_select_own_approved
    ON public.evaluator_tasks
    FOR SELECT
    TO authenticated
    USING (
        auth.uid() = evaluator_id
        AND EXISTS (
            SELECT 1
            FROM public.users u
            WHERE u.id = auth.uid()
              AND u.role = 'evaluator'
              AND u.evaluator_status = 'approved'
        )
    );

-- 7. `public.evaluator_cooldowns`: Evaluator can read only their own cooldown rows
DROP POLICY IF EXISTS evaluator_cooldowns_select_own ON public.evaluator_cooldowns;
CREATE POLICY evaluator_cooldowns_select_own
    ON public.evaluator_cooldowns
    FOR SELECT
    TO authenticated
    USING (auth.uid() = evaluator_id);

-- 8. `public.inspections`: Evaluator can read only their own submitted inspections
DROP POLICY IF EXISTS inspections_select_own ON public.inspections;
CREATE POLICY inspections_select_own
    ON public.inspections
    FOR SELECT
    TO authenticated
    USING (auth.uid() = evaluator_id);

-- -----------------------------------------------------------------------------
-- STEP 5: Private Storage Bucket Policies (`storage.objects`)
-- All uploads (`POST /api/v1/evaluators/documents`) and 60-second admin signed
-- preview URLs (`GET /api/v1/admin/evaluators/{id}/document`) are executed by
-- the FastAPI backend using server-only credentials. Direct client access to
-- `evaluator-ids` and `inspection-evidence` is denied.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'storage' AND table_name = 'objects'
    ) THEN
        DROP POLICY IF EXISTS evaluator_ids_deny_client_select ON storage.objects;
        DROP POLICY IF EXISTS evaluator_ids_deny_client_insert ON storage.objects;
        DROP POLICY IF EXISTS evaluator_ids_deny_client_update ON storage.objects;
        DROP POLICY IF EXISTS evaluator_ids_deny_client_delete ON storage.objects;

        CREATE POLICY evaluator_ids_deny_client_select
            ON storage.objects
            AS RESTRICTIVE
            FOR SELECT
            TO anon, authenticated
            USING (bucket_id NOT IN ('evaluator-ids', 'inspection-evidence'));

        CREATE POLICY evaluator_ids_deny_client_insert
            ON storage.objects
            AS RESTRICTIVE
            FOR INSERT
            TO anon, authenticated
            WITH CHECK (bucket_id NOT IN ('evaluator-ids', 'inspection-evidence'));

        CREATE POLICY evaluator_ids_deny_client_update
            ON storage.objects
            AS RESTRICTIVE
            FOR UPDATE
            TO anon, authenticated
            USING (bucket_id NOT IN ('evaluator-ids', 'inspection-evidence'));

        CREATE POLICY evaluator_ids_deny_client_delete
            ON storage.objects
            AS RESTRICTIVE
            FOR DELETE
            TO anon, authenticated
            USING (bucket_id NOT IN ('evaluator-ids', 'inspection-evidence'));
    END IF;
END $$;

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES (For Shabaz after applying in Supabase SQL Editor)
-- =============================================================================
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public'
--   AND tablename IN (
--       'users',
--       'evaluator_verifications',
--       'webauthn_credentials',
--       'webauthn_challenges',
--       'audit_logs',
--       'evaluator_tasks',
--       'evaluator_cooldowns',
--       'inspections'
--   )
-- ORDER BY tablename;

