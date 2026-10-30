"""In-memory repositories for Evaluator Authentication, WebAuthn, ID Verification,
and Audit Logging.

OWNER: Ibrahim

Strictly for development and deterministic automated tests (`APP_ENV == 'development'`).
Production environments fail closed if SQL persistence is unavailable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
    AuditAction,
    AuditTargetType,
    EvaluatorLifecycleStatus,
    UserRole,
    VerificationStatus,
    WebAuthnChallengePurpose,
)
from app.modules.evaluator.exceptions import (
    AuditLogImmutableError,
    EvaluatorConflictError,
)


class InMemoryEvaluatorUserRepository:
    def __init__(self) -> None:
        self._items: dict[str, EvaluatorUserRecord] = {}

    def clear(self) -> None:
        self._items.clear()

    def get(self, user_id: str) -> EvaluatorUserRecord | None:
        return self._items.get(user_id)

    def get_by_email(self, email: str) -> EvaluatorUserRecord | None:
        target = email.strip().lower()
        for rec in self._items.values():
            if rec.email.strip().lower() == target:
                return rec
        return None

    def get_by_application_reference(
        self, reference: str
    ) -> EvaluatorUserRecord | None:
        target = reference.strip().upper()
        for rec in self._items.values():
            if (
                rec.application_reference
                and rec.application_reference.upper() == target
            ):
                return rec
        return None

    def list_evaluators(
        self,
        *,
        status: EvaluatorLifecycleStatus | None = None,
        operating_area: str | None = None,
        search: str | None = None,
    ) -> list[EvaluatorUserRecord]:
        results: list[EvaluatorUserRecord] = []
        search_q = search.strip().lower() if search else None
        area_q = operating_area.strip().lower() if operating_area else None

        for rec in self._items.values():
            if rec.role != UserRole.EVALUATOR:
                continue
            if status is not None and rec.evaluator_status != status:
                continue
            if area_q and (rec.operating_area or "").strip().lower() != area_q:
                continue
            if search_q:
                haystack = " ".join(
                    filter(
                        None,
                        [
                            rec.full_name,
                            rec.email,
                            rec.phone,
                            rec.application_reference,
                            rec.operating_area,
                        ],
                    )
                ).lower()
                if search_q not in haystack:
                    continue
            results.append(rec)

        return sorted(results, key=lambda r: r.created_at, reverse=True)

    def upsert(self, record: EvaluatorUserRecord) -> EvaluatorUserRecord:
        if record.application_reference:
            existing_ref = self.get_by_application_reference(
                record.application_reference
            )
            if existing_ref is not None and existing_ref.id != record.id:
                raise EvaluatorConflictError(
                    f"Application reference '{record.application_reference}' already exists."
                )
        self._items[record.id] = record
        return record


class InMemoryEvaluatorVerificationRepository:
    def __init__(self) -> None:
        self._items: dict[str, EvaluatorVerificationRecord] = {}

    def clear(self) -> None:
        self._items.clear()

    def get(self, verification_id: str) -> EvaluatorVerificationRecord | None:
        return self._items.get(verification_id)

    def list_for_evaluator(
        self, evaluator_id: str
    ) -> list[EvaluatorVerificationRecord]:
        rows = [
            r for r in self._items.values() if r.evaluator_id == evaluator_id
        ]
        return sorted(rows, key=lambda r: r.created_at, reverse=True)

    def get_latest_for_evaluator(
        self, evaluator_id: str
    ) -> EvaluatorVerificationRecord | None:
        rows = self.list_for_evaluator(evaluator_id)
        return rows[0] if rows else None

    def list_expired_unpurged(
        self, now: datetime
    ) -> list[EvaluatorVerificationRecord]:
        expired: list[EvaluatorVerificationRecord] = []
        for rec in self._items.values():
            if (
                rec.purged_at is None
                and rec.retention_expires_at is not None
                and rec.retention_expires_at <= now
                and rec.verification_status
                in (VerificationStatus.APPROVED, VerificationStatus.REJECTED)
            ):
                expired.append(rec)
        return sorted(expired, key=lambda r: r.created_at)

    def upsert(
        self, record: EvaluatorVerificationRecord
    ) -> EvaluatorVerificationRecord:
        self._items[record.id] = record
        return record


class InMemoryWebAuthnCredentialRepository:
    def __init__(self) -> None:
        self._items: dict[str, WebAuthnCredentialRecord] = {}

    def clear(self) -> None:
        self._items.clear()

    def get_by_id(self, row_id: str) -> WebAuthnCredentialRecord | None:
        return self._items.get(row_id)

    def get_by_credential_id(
        self, credential_id: str
    ) -> WebAuthnCredentialRecord | None:
        for rec in self._items.values():
            if rec.credential_id == credential_id:
                return rec
        return None

    def list_for_user(
        self, user_id: str, *, active_only: bool = True
    ) -> list[WebAuthnCredentialRecord]:
        rows: list[WebAuthnCredentialRecord] = []
        for rec in self._items.values():
            if rec.user_id != user_id:
                continue
            if active_only and rec.revoked_at is not None:
                continue
            rows.append(rec)
        return sorted(rows, key=lambda r: r.created_at, reverse=True)

    def upsert(self, record: WebAuthnCredentialRecord) -> WebAuthnCredentialRecord:
        existing_cred = self.get_by_credential_id(record.credential_id)
        if existing_cred is not None and existing_cred.id != record.id:
            raise EvaluatorConflictError(
                "WebAuthn credential_id is already registered."
            )
        self._items[record.id] = record
        return record


class InMemoryWebAuthnChallengeRepository:
    def __init__(self) -> None:
        self._items: dict[str, WebAuthnChallengeRecord] = {}

    def clear(self) -> None:
        self._items.clear()

    def create(self, record: WebAuthnChallengeRecord) -> WebAuthnChallengeRecord:
        if self.get_by_challenge(record.challenge) is not None:
            raise EvaluatorConflictError("Duplicate WebAuthn challenge.")
        self._items[record.id] = record
        return record

    def get_by_challenge(self, challenge: str) -> WebAuthnChallengeRecord | None:
        for rec in self._items.values():
            if rec.challenge == challenge:
                return rec
        return None

    def consume_atomically(
        self,
        *,
        challenge: str,
        user_id: str,
        purpose: WebAuthnChallengePurpose,
        now: datetime,
    ) -> WebAuthnChallengeRecord | None:
        rec = self.get_by_challenge(challenge)
        if rec is None:
            return None
        if rec.user_id != user_id:
            return None
        if rec.purpose != purpose:
            return None
        if rec.consumed_at is not None:
            return None
        if rec.expires_at <= now:
            return None

        consumed = rec.model_copy(update={"consumed_at": now})
        self._items[rec.id] = consumed
        return consumed


class InMemoryAuditLogRepository:
    """Append-only audit log store matching `public.audit_logs` + `trg_audit_logs_immutable`."""

    def __init__(self) -> None:
        self._items: list[AuditLogRecord] = []

    def clear(self) -> None:
        self._items.clear()

    def append(self, record: AuditLogRecord) -> AuditLogRecord:
        self._items.append(record)
        return record

    def list_logs(
        self,
        *,
        target_type: AuditTargetType | None = None,
        target_id: str | None = None,
        actor_id: str | None = None,
        action: AuditAction | None = None,
    ) -> list[AuditLogRecord]:
        filtered: list[AuditLogRecord] = []
        for rec in self._items:
            if target_type is not None and rec.target_type != target_type:
                continue
            if target_id is not None and rec.target_id != target_id:
                continue
            if actor_id is not None and rec.actor_id != actor_id:
                continue
            if action is not None and rec.action != action:
                continue
            filtered.append(rec)
        return sorted(filtered, key=lambda r: r.created_at, reverse=True)

    def update(self, log_id: str, **changes: Any) -> None:
        raise AuditLogImmutableError(
            "public.audit_logs is append-only; UPDATE and DELETE are forbidden."
        )

    def delete(self, log_id: str) -> None:
        raise AuditLogImmutableError(
            "public.audit_logs is append-only; UPDATE and DELETE are forbidden."
        )


class InMemoryEvaluatorTaskRepository:
    def __init__(self) -> None:
        self._items: dict[str, EvaluatorTaskRecord] = {}

    def clear(self) -> None:
        self._items.clear()

    def get(self, task_id: str) -> EvaluatorTaskRecord | None:
        return self._items.get(task_id)

    def list_for_evaluator(self, evaluator_id: str) -> list[EvaluatorTaskRecord]:
        rows = [
            t for t in self._items.values() if t.evaluator_id == evaluator_id
        ]
        return sorted(rows, key=lambda r: r.assigned_at, reverse=True)

    def upsert(self, record: EvaluatorTaskRecord) -> EvaluatorTaskRecord:
        self._items[record.id] = record
        return record


class InMemoryEvaluatorCooldownRepository:
    def __init__(self) -> None:
        self._items: dict[str, EvaluatorCooldownRecord] = {}

    def clear(self) -> None:
        self._items.clear()

    def get_active_cooldown(
        self, evaluator_id: str, toilet_id: str, now: datetime
    ) -> EvaluatorCooldownRecord | None:
        for rec in self._items.values():
            if (
                rec.evaluator_id == evaluator_id
                and rec.toilet_id == toilet_id
                and rec.cooldown_until > now
            ):
                return rec
        return None

    def list_for_evaluator(
        self, evaluator_id: str
    ) -> list[EvaluatorCooldownRecord]:
        rows = [
            c for c in self._items.values() if c.evaluator_id == evaluator_id
        ]
        return sorted(rows, key=lambda r: r.cooldown_until, reverse=True)

    def upsert(self, record: EvaluatorCooldownRecord) -> EvaluatorCooldownRecord:
        self._items[record.id] = record
        return record


class InMemoryEvaluatorInspectionRepository:
    def __init__(self) -> None:
        self._items: dict[str, EvaluatorInspectionRecord] = {}

    def clear(self) -> None:
        self._items.clear()

    def get(self, inspection_id: str) -> EvaluatorInspectionRecord | None:
        return self._items.get(inspection_id)

    def get_by_idempotency_key(
        self, key: str
    ) -> EvaluatorInspectionRecord | None:
        for rec in self._items.values():
            if rec.submission_idempotency_key == key:
                return rec
        return None

    def list_for_evaluator(
        self, evaluator_id: str
    ) -> list[EvaluatorInspectionRecord]:
        rows = [
            i for i in self._items.values() if i.evaluator_id == evaluator_id
        ]
        return sorted(rows, key=lambda r: r.submitted_at, reverse=True)

    def create(
        self, record: EvaluatorInspectionRecord
    ) -> EvaluatorInspectionRecord:
        if record.submission_idempotency_key:
            existing = self.get_by_idempotency_key(
                record.submission_idempotency_key
            )
            if existing is not None:
                return existing
        self._items[record.id] = record
        return record

