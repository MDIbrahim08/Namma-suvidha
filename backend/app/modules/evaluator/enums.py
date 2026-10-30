"""Enumerations for Evaluator Authentication, Onboarding, WebAuthn, and Audit Logging.

OWNER: Ibrahim (Evaluator workflow integration)
COORDINATES WITH: Shabaz (Auth & RLS), Shubham (Database Schema & Intelligence)
"""

from enum import StrEnum


class UserRole(StrEnum):
    CITIZEN = "citizen"
    EVALUATOR = "evaluator"
    GOVERNMENT = "government"
    ADMIN = "admin"


class EvaluatorLifecycleStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED_PURGED = "expired_purged"


class IDDocumentType(StrEnum):
    AADHAAR_REDACTED = "aadhaar_redacted"
    VOTER_ID = "voter_id"
    DRIVING_LICENCE = "driving_licence"
    PASSPORT = "passport"
    PAN_CARD = "pan_card"
    LEGACY_MIGRATED = "legacy_migrated"


class AllowedIDMimeType(StrEnum):
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"
    PDF = "application/pdf"


class WebAuthnChallengePurpose(StrEnum):
    REGISTRATION = "registration"
    AUTHENTICATION = "authentication"
    INSPECTION_SUBMIT = "inspection_submit"


class WebAuthnMigrationSource(StrEnum):
    NATIVE = "native"
    LEGACY_USERS_TABLE = "legacy_users_table"


class EvaluatorTaskStatus(StrEnum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AuditAction(StrEnum):
    EVALUATOR_REGISTERED = "evaluator.registered"
    DOCUMENT_UPLOADED = "evaluator.document_uploaded"
    DOCUMENT_PREVIEWED = "evaluator.document_previewed"
    DOCUMENT_PURGED = "evaluator.document_purged"
    PASSKEY_REGISTERED = "evaluator.passkey_registered"
    PASSKEY_REVOKED = "evaluator.passkey_revoked"
    LEGACY_PASSKEY_CALIBRATED = "evaluator.legacy_passkey_calibrated"
    PASSKEY_AUTHENTICATED = "evaluator.passkey_authenticated"
    PASSKEY_SIGN_COUNT_ANOMALY = "security.passkey_sign_count_anomaly"
    EVALUATOR_APPROVED = "evaluator.approved"
    EVALUATOR_REJECTED = "evaluator.rejected"
    EVALUATOR_RESUBMITTED = "evaluator.resubmitted"
    EVALUATOR_SUSPENDED = "evaluator.suspended"
    EVALUATOR_REINSTATED = "evaluator.reinstated"
    TASK_ACCEPTED = "evaluator.task_accepted"
    INSPECTION_SUBMITTED = "evaluator.inspection_submitted"
    PRIVILEGED_ACCESS_DENIED = "security.privileged_access_denied"


class AuditTargetType(StrEnum):
    EVALUATOR_ACCOUNT = "evaluator_account"
    IDENTITY_DOCUMENT = "identity_document"
    WEBAUTHN_PASSKEY = "webauthn_passkey"
    EVALUATOR_TASK = "evaluator_task"
    INSPECTION = "inspection"

