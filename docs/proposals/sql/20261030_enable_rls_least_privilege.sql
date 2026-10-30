-- =============================================================================
-- NAMMA SUVIDHA — SUPABASE ROW LEVEL SECURITY (RLS) MIGRATION PROPOSAL
-- =============================================================================
-- STATUS: PROPOSED — AWAITING SHABAZ'S REVIEW & APPROVAL
-- DO NOT EXECUTE AUTOMATICALLY FROM APPLICATION CODE.
--
-- Purpose:
--   1. Enable Row Level Security (RLS) on all 7 existing public tables.
--   2. Revoke direct anonymous/authenticated access to sensitive PII columns
--      (operator emails/phones on `public.toilets`, identity docs & WebAuthn keys
--      on `public.users`).
--   3. Create strict least-privilege SELECT policies for authenticated users
--      while keeping all writes and privileged reads mediated by the FastAPI
--      backend (`service_role` / postgres pooler).
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- STEP 1: Enable Row Level Security (RLS) on all 7 public tables
-- -----------------------------------------------------------------------------
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.toilets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.citizen_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluator_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluator_cooldowns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inspections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.maintenance_tickets ENABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- STEP 2: Revoke broad table-level write privileges from `anon` and `authenticated`
-- All inserts, updates, and deletes must go through the FastAPI backend so that
-- rate limiting, 45-day cooldowns, score computation, and state machines apply.
-- -----------------------------------------------------------------------------
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.users FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.toilets FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.citizen_reports FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.evaluator_tasks FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.evaluator_cooldowns FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.inspections FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.maintenance_tickets FROM anon, authenticated;

-- -----------------------------------------------------------------------------
-- STEP 3: Column-level PII protection on `public.toilets` and `public.users`
-- PostgreSQL RLS is row-level; revoking column-level SELECT prevents PostgREST
-- callers from reading operator contact PII or WebAuthn/ID document secrets.
-- -----------------------------------------------------------------------------
REVOKE SELECT ON public.toilets FROM anon, authenticated;
GRANT SELECT (
    id,
    name,
    address,
    ward_name,
    location,
    is_free,
    fee_amount,
    toilet_type,
    has_wheelchair_access,
    has_water,
    has_handwash,
    has_gender_separation,
    has_baby_changing,
    has_sanitary_napkin_vending,
    overall_score,
    evaluator_score_avg,
    citizen_score_avg,
    status,
    last_inspected_at,
    created_at,
    updated_at
) ON public.toilets TO anon, authenticated;

REVOKE SELECT ON public.users FROM anon;
REVOKE SELECT ON public.users FROM authenticated;
GRANT SELECT (
    id,
    full_name,
    email,
    phone,
    role,
    evaluator_status,
    wallet_balance,
    created_at,
    updated_at
) ON public.users TO authenticated;
-- Note: `id_document_url`, `webauthn_credential_id`, and `webauthn_public_key`
-- are intentionally excluded from direct `authenticated` PostgREST SELECT.

-- -----------------------------------------------------------------------------
-- STEP 4: Least-Privilege Row Level Security Policies
-- -----------------------------------------------------------------------------

-- 1. `public.users`: Authenticated user may read ONLY their own user profile row
DROP POLICY IF EXISTS users_select_own ON public.users;
CREATE POLICY users_select_own
    ON public.users
    FOR SELECT
    TO authenticated
    USING (auth.uid() = id);

-- 2. `public.toilets`: Public read of non-PII columns (column grant above strips operator PII)
DROP POLICY IF EXISTS toilets_select_public ON public.toilets;
CREATE POLICY toilets_select_public
    ON public.toilets
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- 3. `public.citizen_reports`: Authenticated citizen may read ONLY their own reports
DROP POLICY IF EXISTS citizen_reports_select_own ON public.citizen_reports;
CREATE POLICY citizen_reports_select_own
    ON public.citizen_reports
    FOR SELECT
    TO authenticated
    USING (user_id IS NOT NULL AND auth.uid() = user_id);

-- 4. `public.evaluator_tasks`: Authenticated evaluator may read ONLY their own assigned tasks
DROP POLICY IF EXISTS evaluator_tasks_select_own ON public.evaluator_tasks;
CREATE POLICY evaluator_tasks_select_own
    ON public.evaluator_tasks
    FOR SELECT
    TO authenticated
    USING (auth.uid() = evaluator_id);

-- 5. `public.evaluator_cooldowns`: Authenticated evaluator may read ONLY their own cooldowns
DROP POLICY IF EXISTS evaluator_cooldowns_select_own ON public.evaluator_cooldowns;
CREATE POLICY evaluator_cooldowns_select_own
    ON public.evaluator_cooldowns
    FOR SELECT
    TO authenticated
    USING (auth.uid() = evaluator_id);

-- 6. `public.inspections`: Authenticated evaluator may read ONLY their own inspections
DROP POLICY IF EXISTS inspections_select_own ON public.inspections;
CREATE POLICY inspections_select_own
    ON public.inspections
    FOR SELECT
    TO authenticated
    USING (auth.uid() = evaluator_id);

-- 7. `public.maintenance_tickets`: No direct client access; all access is mediated
--    by the FastAPI Government Monitoring module (`require_government_user`).
DROP POLICY IF EXISTS maintenance_tickets_deny_client ON public.maintenance_tickets;

COMMIT;

-- =============================================================================
-- POST-MIGRATION VERIFICATION QUERIES (Run in Supabase SQL Editor)
-- =============================================================================
-- 1. Confirm `rowsecurity = true` on all 7 tables:
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- ORDER BY tablename;
--
-- 2. Inspect active RLS policies:
-- SELECT tablename, policyname, permissive, roles, cmd, qual
-- FROM pg_policies
-- WHERE schemaname = 'public'
-- ORDER BY tablename, policyname;

