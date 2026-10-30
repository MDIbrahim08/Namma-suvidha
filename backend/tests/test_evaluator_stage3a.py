"""Stage 3A tests: Evaluator domain models, enums, repository interfaces,
in-memory and SQL-ready adapters, append-only audit enforcement, and
production fail-closed behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.evaluator.config import (
    EvaluatorModuleSettings,
    validate_evaluator_startup,
)
from app.modules.evaluator.domain import (
    AuditLogRecord,
    EvaluatorCooldownRecord,
    EvaluatorInspectionRecord,
    EvaluatorTaskRecord,
    EvaluatorUserRecord,
    EvaluatorVerificationRecord,
    WebAuthnChallengeRecord,
    WebAuthnCredentialRecord,
)
from app.modules.evaluator.enums import (
    AllowedIDMimeType,
    AuditAction,
    AuditTargetType,
    EvaluatorLifecycleStatus,
    IDDocumentType,
    UserRole,
    VerificationStatus,
    WebAuthnChallengePurpose,
    WebAuthnMigrationSource,
)
from app.modules.evaluator.exceptions import (
    AuditLogImmutableError,
    EvaluatorConflictError,
    EvaluatorSchemaPendingError,
)
from app.modules.evaluator.repositories import (
    get_evaluator_memory_bundle,
    get_evaluator_repository_bundle,
)


def test_stage3a_production_fails_closed_when_memory_or_pending_sql() -> None:
    """Verify Condition 2: In-memory storage is for development and deterministic
    tests only. Production must fail closed if SQL persistence is unavailable.
    """
    settings_mem = EvaluatorModuleSettings(REPOSITORY_BACKEND="memory")
    with pytest.raises(EvaluatorSchemaPendingError, match="forbidden when APP_ENV"):
        validate_evaluator_startup("production", settings_mem)

    with pytest.raises(EvaluatorSchemaPendingError, match="forbidden in production"):
        get_evaluator_repository_bundle("memory", app_env="production")

    with pytest.raises(EvaluatorSchemaPendingError):
        get_evaluator_repository_bundle("sql", app_env="production")


def test_stage3a_user_and_verification_repositories() -> None:
    now = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)
    bundle = get_evaluator_memory_bundle()
    bundle.clear_all()

    user = EvaluatorUserRecord(
        id="eval-001",
        full_name="Asha Rao",
        email="asha.rao@example.com",
        phone="+919876543210",
        role=UserRole.EVALUATOR,
        evaluator_status=EvaluatorLifecycleStatus.PENDING,
        operating_area="Indiranagar Ward 80",
        application_reference="EV-2026-0001",
        email_verified_at=now,
        created_at=now,
        updated_at=now,
    )
    bundle.users.upsert(user)

    assert bundle.users.get("eval-001") == user
    assert bundle.users.get_by_email("ASHA.RAO@example.com") == user
    assert bundle.users.get_by_application_reference("ev-2026-0001") == user

    # Duplicate application reference on a different user must raise conflict
    dup_user = user.model_copy(update={"id": "eval-002", "email": "other@example.com"})
    with pytest.raises(EvaluatorConflictError):
        bundle.users.upsert(dup_user)

    # Verification record & expired unpurged query
    ver = EvaluatorVerificationRecord(
        id="ver-001",
        evaluator_id="eval-001",
        application_reference="EV-2026-0001",
        document_type=IDDocumentType.DRIVING_LICENCE,
        document_storage_path="evaluator-ids/eval-001/ver-001.png",
        mime_type=AllowedIDMimeType.PNG,
        file_size_bytes=2048,
        sha256_checksum="a" * 64,
        verification_status=VerificationStatus.APPROVED,
        reviewed_by="admin-001",
        reviewed_at=now - timedelta(days=8),
        retention_expires_at=now - timedelta(days=1),
        created_at=now - timedelta(days=9),
        updated_at=now - timedelta(days=8),
    )
    bundle.verifications.upsert(ver)
    assert bundle.verifications.get_latest_for_evaluator("eval-001") == ver
    expired = bundle.verifications.list_expired_unpurged(now)
    assert len(expired) == 1
    assert expired[0].id == "ver-001"


def test_stage3a_webauthn_credential_and_atomic_challenge_consumption() -> None:
    now = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)
    bundle = get_evaluator_memory_bundle()
    bundle.clear_all()

    cred = WebAuthnCredentialRecord(
        id="cred-row-1",
        user_id="eval-001",
        credential_id="cred-id-abc",
        public_key="cose-key-base64",
        sign_count=0,
        sign_count_initialized=False,
        migration_source=WebAuthnMigrationSource.LEGACY_USERS_TABLE,
        created_at=now,
    )
    bundle.credentials.upsert(cred)

    # Uniqueness enforced across users
    with pytest.raises(EvaluatorConflictError):
        bundle.credentials.upsert(
            cred.model_copy(id="cred-row-2", user_id="eval-002")  # type: ignore[call-arg]
        )

    challenge = WebAuthnChallengeRecord(
        id="chal-1",
        user_id="eval-001",
        challenge="random-challenge-xyz",
        purpose=WebAuthnChallengePurpose.AUTHENTICATION,
        rp_id="localhost",
        expected_origin="http://localhost:5173",
        expires_at=now + timedelta(minutes=5),
        created_at=now,
    )
    bundle.challenges.create(challenge)

    # Wrong user or wrong purpose cannot consume
    assert (
        bundle.challenges.consume_atomically(
            challenge="random-challenge-xyz",
            user_id="eval-999",
            purpose=WebAuthnChallengePurpose.AUTHENTICATION,
            now=now,
        )
        is None
    )
    assert (
        bundle.challenges.consume_atomically(
            challenge="random-challenge-xyz",
            user_id="eval-001",
            purpose=WebAuthnChallengePurpose.REGISTRATION,
            now=now,
        )
        is None
    )

    # First valid consume succeeds
    consumed = bundle.challenges.consume_atomically(
        challenge="random-challenge-xyz",
        user_id="eval-001",
        purpose=WebAuthnChallengePurpose.AUTHENTICATION,
        now=now,
    )
    assert consumed is not None
    assert consumed.consumed_at == now

    # Second consume (replay) returns None
    replayed = bundle.challenges.consume_atomically(
        challenge="random-challenge-xyz",
        user_id="eval-001",
        purpose=WebAuthnChallengePurpose.AUTHENTICATION,
        now=now,
    )
    assert replayed is None


def test_stage3a_audit_log_append_only_immutability_and_existing_tables() -> None:
    now = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)
    bundle = get_evaluator_memory_bundle()
    bundle.clear_all()

    log_entry = AuditLogRecord(
        id="aud-001",
        actor_id="admin-001",
        actor_role="admin",
        action=AuditAction.EVALUATOR_APPROVED,
        target_type=AuditTargetType.EVALUATOR_ACCOUNT,
        target_id="eval-001",
        previous_status="pending",
        new_status="approved",
        reason="Verified driving licence",
        metadata={"application_reference": "EV-2026-0001"},
        created_at=now,
    )
    bundle.audit_logs.append(log_entry)
    assert len(bundle.audit_logs.list_logs(target_id="eval-001")) == 1

    with pytest.raises(AuditLogImmutableError):
        bundle.audit_logs.update("aud-001", reason="tampered")

    with pytest.raises(AuditLogImmutableError):
        bundle.audit_logs.delete("aud-001")

    # Existing task, cooldown, and idempotent inspection tables
    task = EvaluatorTaskRecord(
        id="tsk-001",
        toilet_id="tlt-001",
        evaluator_id="eval-001",
        assigned_at=now,
    )
    bundle.tasks.upsert(task)
    assert len(bundle.tasks.list_for_evaluator("eval-001")) == 1

    cooldown = EvaluatorCooldownRecord(
        id="cd-001",
        evaluator_id="eval-001",
        toilet_id="tlt-001",
        last_inspected_at=now,
        cooldown_until=now + timedelta(days=45),
    )
    bundle.cooldowns.upsert(cooldown)
    assert (
        bundle.cooldowns.get_active_cooldown("eval-001", "tlt-001", now)
        is not None
    )

    insp = EvaluatorInspectionRecord(
        id="insp-001",
        task_id="tsk-001",
        toilet_id="tlt-001",
        evaluator_id="eval-001",
        checklist_answers={"water": True},
        submission_idempotency_key="idem-key-1",
        webauthn_credential_id_used="cred-id-abc",
        webauthn_challenge_id="chal-1",
        submitted_at=now,
    )
    saved1 = bundle.inspections.create(insp)
    saved2 = bundle.inspections.create(
        insp.model_copy(update={"id": "insp-002"})
    )
    assert saved1.id == "insp-001"
    assert saved2.id == "insp-001"  # Idempotent duplicate prevented

