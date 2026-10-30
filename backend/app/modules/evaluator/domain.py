"""Domain models for the Evaluator Authentication, WebAuthn, ID Verification,
and Audit Logging module.

OWNER: Ibrahim
COORDINATES WITH: Shubham (database schema owner) & Shabaz (auth/RLS owner)

Reuses canonical `public.users` and preserves existing `public.evaluator_tasks`,
`public.evaluator_cooldowns`, and `public.inspections`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.evaluator.enums import (
    AllowedIDMimeType,
    AuditAction,
    AuditTargetType,
    EvaluatorLifecycleStatus,
    EvaluatorTaskStatus,
    IDDocumentType,
    UserRole,
    VerificationStatus,
    WebAuthnChallengePurpose,
    WebAuthnMigrationSource,
)


class EvaluatorUserRecord(BaseModel):
    """Represents a row in canonical `public.users` (with additive Stage 2 columns)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    full_name: str
    email: str
    phone: str | None = None
    role: UserRole = UserRole.EVALUATOR
    evaluator_status: EvaluatorLifecycleStatus | None = (
        EvaluatorLifecycleStatus.PENDING
    )
    operating_area: str | None = None
    preferred_language: str = "en"
    application_reference: str | None = None
    email_verified_at: datetime | None = None
    status_updated_by: str | None = None
    status_updated_at: datetime | None = None
    status_reason: str | None = None
    # Legacy columns on `public.users` preserved for backward compatibility
    id_document_url: str | None = None
    webauthn_credential_id: str | None = None
    webauthn_public_key: str | None = None
    wallet_balance: float = 0.0
    created_at: datetime
    updated_at: datetime


class EvaluatorVerificationRecord(BaseModel):
    """Represents a row in `public.evaluator_verifications`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    evaluator_id: str
    application_reference: str
    document_type: IDDocumentType
    document_storage_bucket: str = "evaluator-ids"
    document_storage_path: str
    mime_type: AllowedIDMimeType
    file_size_bytes: int = Field(..., gt=0, le=5_242_880)
    sha256_checksum: str = Field(..., min_length=64, max_length=64)
    verification_status: VerificationStatus = VerificationStatus.PENDING
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    retention_expires_at: datetime | None = None
    purged_at: datetime | None = None
    deletion_verified: bool = False
    created_at: datetime
    updated_at: datetime


class WebAuthnCredentialRecord(BaseModel):
    """Represents a row in `public.webauthn_credentials`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str
    credential_id: str
    public_key: str
    sign_count: int = Field(default=0, ge=0)
    sign_count_initialized: bool = True
    migration_source: WebAuthnMigrationSource = WebAuthnMigrationSource.NATIVE
    aaguid: str | None = None
    transports: list[str] = Field(default_factory=list)
    device_name: str = "Registered Passkey"
    backed_up: bool = False
    user_verified_on_register: bool = True
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revoke_reason: str | None = None


class WebAuthnChallengeRecord(BaseModel):
    """Represents a row in `public.webauthn_challenges`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str
    challenge: str
    purpose: WebAuthnChallengePurpose
    operation_context: dict[str, Any] = Field(default_factory=dict)
    rp_id: str
    expected_origin: str
    user_verification: str = "required"
    expires_at: datetime
    consumed_at: datetime | None = None
    created_at: datetime


class AuditLogRecord(BaseModel):
    """Represents an append-only row in `public.audit_logs`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    actor_id: str | None
    actor_role: str
    action: AuditAction
    target_type: AuditTargetType
    target_id: str
    previous_status: str | None = None
    new_status: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EvaluatorTaskRecord(BaseModel):
    """Represents an existing row in `public.evaluator_tasks` (owned by Shubham)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    toilet_id: str
    evaluator_id: str
    status: EvaluatorTaskStatus = EvaluatorTaskStatus.ASSIGNED
    photo_challenge_prompt: str | None = None
    assigned_at: datetime
    due_at: datetime | None = None
    completed_at: datetime | None = None


class EvaluatorCooldownRecord(BaseModel):
    """Represents an existing row in `public.evaluator_cooldowns` (45-day rule owned by Shubham)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    evaluator_id: str
    toilet_id: str
    last_inspected_at: datetime
    cooldown_until: datetime


class EvaluatorInspectionRecord(BaseModel):
    """Represents an existing row in `public.inspections` with WebAuthn & idempotency links."""

    model_config = ConfigDict(extra="forbid")

    id: str
    task_id: str | None = None
    toilet_id: str
    evaluator_id: str
    checklist_answers: dict[str, Any] = Field(default_factory=dict)
    evidence_urls: list[str] = Field(default_factory=list)
    notes: str | None = None
    submission_idempotency_key: str | None = None
    webauthn_credential_id_used: str | None = None
    webauthn_challenge_id: str | None = None
    submitted_at: datetime

