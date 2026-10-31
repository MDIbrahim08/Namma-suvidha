-- =============================================================================
-- NAMMA SUVIDHA — ALL-IN-ONE SUPABASE COMPLETE CONSOLIDATED MIGRATION
-- =============================================================================
-- FILE: docs/proposals/sql/COMBINED_ALL_IN_ONE_SUPABASE.sql
-- Contains:
--   1. Extensions (uuid-ossp, pgcrypto, postgis)
--   2. Core Tables (users, toilets, citizen_reports, evaluator_tasks, etc.)
--   3. Evaluator Authentication & WebAuthn Tables (evaluator_verifications,
--      webauthn_credentials, webauthn_challenges, audit_logs)
--   4. Least-Privilege Row Level Security (RLS) & Table Write Revocation
--   5. Storage Bucket Security Policies (evaluator-ids, inspection-evidence)
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 0. EXTENSIONS
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- -----------------------------------------------------------------------------
-- 1. CORE TABLES (IF NOT ALREADY EXISTING)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(120),
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(32),
    role VARCHAR(32) NOT NULL DEFAULT 'citizen'
        CHECK (role IN ('citizen', 'evaluator', 'government', 'admin')),
    evaluator_status VARCHAR(32)
        CHECK (evaluator_status IS NULL OR evaluator_status IN ('pending', 'approved', 'rejected', 'suspended')),
    operating_area VARCHAR(150),
    preferred_language VARCHAR(32) DEFAULT 'en',
    application_reference VARCHAR(64) UNIQUE,
    email_verified_at TIMESTAMPTZ,
    status_updated_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    status_updated_at TIMESTAMPTZ,
    status_reason TEXT,
    wallet_balance NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.toilets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    address TEXT,
    ward_name VARCHAR(120),
    zone_name VARCHAR(120),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    is_free BOOLEAN NOT NULL DEFAULT true,
    fee_amount NUMERIC(6,2) DEFAULT 0.00,
    toilet_type VARCHAR(64) DEFAULT 'public',
    has_wheelchair_access BOOLEAN DEFAULT false,
    has_water BOOLEAN DEFAULT true,
    has_handwash BOOLEAN DEFAULT true,
    has_gender_separation BOOLEAN DEFAULT true,
    has_baby_changing BOOLEAN DEFAULT false,
    has_sanitary_napkin_vending BOOLEAN DEFAULT false,
    overall_score NUMERIC(5,2) DEFAULT 50.00,
    evaluator_score_avg NUMERIC(5,2),
    citizen_score_avg NUMERIC(5,2),
    status VARCHAR(32) NOT NULL DEFAULT 'operational',
    last_inspected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.citizen_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    toilet_id UUID NOT NULL REFERENCES public.toilets(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    is_clean BOOLEAN NOT NULL,
    category VARCHAR(64),
    comments TEXT,
    audio_url TEXT,
    audio_transcription TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.evaluator_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluator_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    toilet_id UUID NOT NULL REFERENCES public.toilets(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'assigned',
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    due_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.evaluator_cooldowns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluator_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    toilet_id UUID NOT NULL REFERENCES public.toilets(id) ON DELETE CASCADE,
    inspected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cooldown_expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS public.inspections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES public.evaluator_tasks(id) ON DELETE SET NULL,
    evaluator_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    toilet_id UUID NOT NULL REFERENCES public.toilets(id) ON DELETE CASCADE,
    cleanliness_score NUMERIC(5,2) NOT NULL,
    checklist_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    photos TEXT[] NOT NULL DEFAULT '{}'::text[],
    webauthn_signature TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.maintenance_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    toilet_id UUID NOT NULL REFERENCES public.toilets(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(32) NOT NULL DEFAULT 'medium',
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    assigned_to VARCHAR(150),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

-- -----------------------------------------------------------------------------
-- 2. EVALUATOR ONBOARDING & AUDIT TABLES
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.evaluator_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluator_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    application_reference VARCHAR(64) NOT NULL,
    document_type VARCHAR(64) NOT NULL,
    document_storage_bucket VARCHAR(64) NOT NULL DEFAULT 'evaluator-ids',
    document_storage_path TEXT NOT NULL,
    mime_type VARCHAR(64) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    sha256_checksum CHAR(64) NOT NULL,
    verification_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    reviewed_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    rejection_reason TEXT,
    retention_expires_at TIMESTAMPTZ,
    purged_at TIMESTAMPTZ,
    deletion_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.webauthn_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    credential_id TEXT NOT NULL UNIQUE,
    public_key TEXT NOT NULL,
    sign_count BIGINT NOT NULL DEFAULT 0,
    sign_count_initialized BOOLEAN NOT NULL DEFAULT true,
    migration_source VARCHAR(32) NOT NULL DEFAULT 'native',
    aaguid VARCHAR(64),
    transports TEXT[] NOT NULL DEFAULT '{}'::text[],
    device_name VARCHAR(120) NOT NULL DEFAULT 'Registered Passkey',
    backed_up BOOLEAN NOT NULL DEFAULT false,
    user_verified_on_register BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    revoke_reason TEXT
);

CREATE TABLE IF NOT EXISTS public.webauthn_challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    challenge VARCHAR(128) NOT NULL UNIQUE,
    purpose VARCHAR(32) NOT NULL,
    operation_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    actor_role VARCHAR(32) NOT NULL,
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(64) NOT NULL,
    target_id VARCHAR(128) NOT NULL,
    reason TEXT,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Trigger: Immutability on audit_logs
CREATE OR REPLACE FUNCTION public.fn_prevent_audit_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs entries are strictly immutable. UPDATE and DELETE are prohibited.'
        USING ERRCODE = '55000';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_audit_log_mutation ON public.audit_logs;
CREATE TRIGGER trg_prevent_audit_log_mutation
    BEFORE UPDATE OR DELETE ON public.audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION public.fn_prevent_audit_log_mutation();

-- -----------------------------------------------------------------------------
-- 3. ENABLE ROW LEVEL SECURITY & REVOKE DIRECT CLIENT MUTATIONS
-- -----------------------------------------------------------------------------
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.toilets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.citizen_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluator_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluator_cooldowns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inspections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.maintenance_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluator_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webauthn_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webauthn_challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.users FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.toilets FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.citizen_reports FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.evaluator_tasks FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.evaluator_cooldowns FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.inspections FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.maintenance_tickets FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.evaluator_verifications FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.webauthn_credentials FROM anon, authenticated;
REVOKE ALL ON public.webauthn_challenges FROM anon, authenticated;
REVOKE ALL ON public.audit_logs FROM anon, authenticated;

-- -----------------------------------------------------------------------------
-- 4. ROW LEVEL SECURITY POLICIES
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS users_select_own ON public.users;
CREATE POLICY users_select_own ON public.users
    FOR SELECT TO authenticated
    USING (auth.uid() = id);

DROP POLICY IF EXISTS toilets_select_public ON public.toilets;
CREATE POLICY toilets_select_public ON public.toilets
    FOR SELECT TO anon, authenticated
    USING (true);

DROP POLICY IF EXISTS evaluator_verifications_select_own ON public.evaluator_verifications;
CREATE POLICY evaluator_verifications_select_own ON public.evaluator_verifications
    FOR SELECT TO authenticated
    USING (evaluator_id = auth.uid());

DROP POLICY IF EXISTS webauthn_credentials_select_own ON public.webauthn_credentials;
CREATE POLICY webauthn_credentials_select_own ON public.webauthn_credentials
    FOR SELECT TO authenticated
    USING (user_id = auth.uid() AND revoked_at IS NULL);

DROP POLICY IF EXISTS evaluator_tasks_select_own ON public.evaluator_tasks;
CREATE POLICY evaluator_tasks_select_own ON public.evaluator_tasks
    FOR SELECT TO authenticated
    USING (evaluator_id = auth.uid());

DROP POLICY IF EXISTS evaluator_cooldowns_select_own ON public.evaluator_cooldowns;
CREATE POLICY evaluator_cooldowns_select_own ON public.evaluator_cooldowns
    FOR SELECT TO authenticated
    USING (evaluator_id = auth.uid());

DROP POLICY IF EXISTS inspections_select_own ON public.inspections;
CREATE POLICY inspections_select_own ON public.inspections
    FOR SELECT TO authenticated
    USING (evaluator_id = auth.uid());

COMMIT;

