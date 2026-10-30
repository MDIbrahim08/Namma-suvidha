-- =============================================================================
-- NAMMA SUVIDHA — EVALUATOR AUTHENTICATION, WEBAUTHN & AUDIT SCHEMA PROPOSAL
-- =============================================================================
-- FILE: docs/proposals/sql/20261031_evaluator_auth_schema.sql
-- STATUS: PROPOSED — AWAITING SHUBHAM & SHABAZ'S APPROVAL
-- DO NOT EXECUTE AUTOMATICALLY WITHOUT EXPLICIT TEAM APPROVAL.
--
-- Design Summary:
--   1. Reuses canonical `public.users` (does NOT create a duplicate `profiles` table).
--   2. Preserves existing `public.evaluator_tasks`, `public.evaluator_cooldowns`,
--      and `public.inspections`.
--   3. Creates:
--        - `public.evaluator_verifications`
--        - `public.webauthn_credentials`
--        - `public.webauthn_challenges`
--        - `public.audit_logs` (with append-only immutability trigger)
--   4. Safely backfills any existing `users.webauthn_credential_id` /
--      `users.webauthn_public_key` and `users.id_document_url` rows without
--      deleting or overwriting legacy columns.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Non-destructive extensions to existing `public.users`
-- -----------------------------------------------------------------------------
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS operating_area VARCHAR(150),
    ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(32) DEFAULT 'en',
    ADD COLUMN IF NOT EXISTS application_reference VARCHAR(64),
    ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS status_updated_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS status_reason TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_application_reference
    ON public.users (application_reference)
    WHERE application_reference IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_users_role_allowed'
    ) THEN
        ALTER TABLE public.users
            ADD CONSTRAINT chk_users_role_allowed
            CHECK (role IN ('citizen', 'evaluator', 'government', 'admin'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_users_evaluator_status_allowed'
    ) THEN
        ALTER TABLE public.users
            ADD CONSTRAINT chk_users_evaluator_status_allowed
            CHECK (
                evaluator_status IS NULL
                OR evaluator_status IN ('pending', 'approved', 'rejected', 'suspended')
            );
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 2. Create `public.evaluator_verifications`
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.evaluator_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluator_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    application_reference VARCHAR(64) NOT NULL,
    document_type VARCHAR(64) NOT NULL
        CHECK (document_type IN (
            'aadhaar_redacted',
            'voter_id',
            'driving_licence',
            'passport',
            'pan_card',
            'legacy_migrated'
        )),
    document_storage_bucket VARCHAR(64) NOT NULL DEFAULT 'evaluator-ids',
    document_storage_path TEXT NOT NULL,
    mime_type VARCHAR(64) NOT NULL
        CHECK (mime_type IN (
            'image/jpeg',
            'image/png',
            'image/webp',
            'application/pdf'
        )),
    file_size_bytes INTEGER NOT NULL
        CHECK (file_size_bytes > 0 AND file_size_bytes <= 5242880),
    sha256_checksum CHAR(64) NOT NULL,
    verification_status VARCHAR(32) NOT NULL DEFAULT 'pending'
        CHECK (verification_status IN (
            'pending',
            'approved',
            'rejected',
            'expired_purged'
        )),
    reviewed_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    rejection_reason TEXT,
    retention_expires_at TIMESTAMPTZ,
    purged_at TIMESTAMPTZ,
    deletion_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evaluator_verifications_evaluator_id
    ON public.evaluator_verifications (evaluator_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_evaluator_verifications_status
    ON public.evaluator_verifications (verification_status, created_at ASC);

-- -----------------------------------------------------------------------------
-- 3. Create `public.webauthn_credentials` (Multi-device passkey store)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.webauthn_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    credential_id TEXT NOT NULL UNIQUE,
    public_key TEXT NOT NULL,
    sign_count BIGINT NOT NULL DEFAULT 0 CHECK (sign_count >= 0),
    sign_count_initialized BOOLEAN NOT NULL DEFAULT true,
    migration_source VARCHAR(32) NOT NULL DEFAULT 'native'
        CHECK (migration_source IN ('native', 'legacy_users_table')),
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

CREATE INDEX IF NOT EXISTS idx_webauthn_credentials_user_active
    ON public.webauthn_credentials (user_id)
    WHERE revoked_at IS NULL;

-- -----------------------------------------------------------------------------
-- 4. Create `public.webauthn_challenges` (Single-use, short-lived challenges)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.webauthn_challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    challenge VARCHAR(128) NOT NULL UNIQUE,
    purpose VARCHAR(32) NOT NULL
        CHECK (purpose IN ('registration', 'authentication', 'inspection_submit')),
    operation_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    rp_id VARCHAR(255) NOT NULL,
    expected_origin VARCHAR(255) NOT NULL,
    user_verification VARCHAR(16) NOT NULL DEFAULT 'required'
        CHECK (user_verification IN ('required', 'preferred')),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_webauthn_challenges_user_purpose
    ON public.webauthn_challenges (user_id, purpose, expires_at DESC);

-- -----------------------------------------------------------------------------
-- 5. Create `public.audit_logs` (Append-only immutable audit log)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    actor_role VARCHAR(32) NOT NULL,
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(64) NOT NULL,
    target_id VARCHAR(128) NOT NULL,
    previous_status VARCHAR(32),
    new_status VARCHAR(32),
    reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_target
    ON public.audit_logs (target_type, target_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_actor
    ON public.audit_logs (actor_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_action
    ON public.audit_logs (action, created_at DESC);

CREATE OR REPLACE FUNCTION public.prevent_audit_log_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'public.audit_logs is append-only; UPDATE and DELETE are forbidden.';
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON public.audit_logs;
CREATE TRIGGER trg_audit_logs_immutable
    BEFORE UPDATE OR DELETE ON public.audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_audit_log_mutation();

-- -----------------------------------------------------------------------------
-- 6. Non-destructive idempotency & WebAuthn audit columns on `public.inspections`
-- -----------------------------------------------------------------------------
ALTER TABLE public.inspections
    ADD COLUMN IF NOT EXISTS submission_idempotency_key VARCHAR(128),
    ADD COLUMN IF NOT EXISTS webauthn_credential_id_used TEXT,
    ADD COLUMN IF NOT EXISTS webauthn_challenge_id UUID
        REFERENCES public.webauthn_challenges(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_inspections_idempotency_key
    ON public.inspections (submission_idempotency_key)
    WHERE submission_idempotency_key IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 7. Safe Legacy Backfill from `public.users` (Preserves all existing data)
-- -----------------------------------------------------------------------------
INSERT INTO public.webauthn_credentials (
    user_id,
    credential_id,
    public_key,
    sign_count,
    sign_count_initialized,
    migration_source,
    device_name,
    created_at
)
SELECT
    u.id,
    u.webauthn_credential_id,
    u.webauthn_public_key,
    0,
    false,
    'legacy_users_table',
    'Legacy Migrated Authenticator',
    u.created_at
FROM public.users u
WHERE u.webauthn_credential_id IS NOT NULL
  AND btrim(u.webauthn_credential_id) <> ''
  AND u.webauthn_public_key IS NOT NULL
  AND btrim(u.webauthn_public_key) <> ''
ON CONFLICT (credential_id) DO NOTHING;

-- Provision private storage buckets (`evaluator-ids` and `inspection-evidence`)
-- if `storage.buckets` is present in the Supabase instance:
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'storage' AND table_name = 'buckets'
    ) THEN
        INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
        VALUES (
            'evaluator-ids',
            'evaluator-ids',
            false,
            5242880,
            ARRAY['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
        )
        ON CONFLICT (id) DO UPDATE
        SET public = false,
            file_size_limit = 5242880,
            allowed_mime_types = ARRAY['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];

        INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
        VALUES (
            'inspection-evidence',
            'inspection-evidence',
            false,
            10485760,
            ARRAY['image/jpeg', 'image/png', 'image/webp']
        )
        ON CONFLICT (id) DO UPDATE
        SET public = false,
            file_size_limit = 10485760,
            allowed_mime_types = ARRAY['image/jpeg', 'image/png', 'image/webp'];
    END IF;
END $$;

COMMIT;

