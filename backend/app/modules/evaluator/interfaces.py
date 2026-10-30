"""Repository protocols and provider interfaces for the Evaluator module.

OWNER: Ibrahim
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

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
    VerificationStatus,
    WebAuthnChallengePurpose,
)


class EvaluatorClock(Protocol):
    def now(self) -> datetime: ...


class SystemEvaluatorClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class EvaluatorUserRepository(Protocol):
    def get(self, user_id: str) -> EvaluatorUserRecord | None: ...

    def get_by_email(self, email: str) -> EvaluatorUserRecord | None: ...

    def get_by_application_reference(
        self, reference: str
    ) -> EvaluatorUserRecord | None: ...

    def list_evaluators(
        self,
        *,
        status: EvaluatorLifecycleStatus | None = None,
        operating_area: str | None = None,
        search: str | None = None,
    ) -> list[EvaluatorUserRecord]: ...

    def upsert(self, record: EvaluatorUserRecord) -> EvaluatorUserRecord: ...


class EvaluatorVerificationRepository(Protocol):
    def get(self, verification_id: str) -> EvaluatorVerificationRecord | None: ...

    def get_latest_for_evaluator(
        self, evaluator_id: str
    ) -> EvaluatorVerificationRecord | None: ...

    def list_for_evaluator(
        self, evaluator_id: str
    ) -> list[EvaluatorVerificationRecord]: ...

    def list_expired_unpurged(
        self, now: datetime
    ) -> list[EvaluatorVerificationRecord]: ...

    def upsert(
        self, record: EvaluatorVerificationRecord
    ) -> EvaluatorVerificationRecord: ...


class WebAuthnCredentialRepository(Protocol):
    def get_by_id(self, row_id: str) -> WebAuthnCredentialRecord | None: ...

    def get_by_credential_id(
        self, credential_id: str
    ) -> WebAuthnCredentialRecord | None: ...

    def list_for_user(
        self, user_id: str, *, active_only: bool = True
    ) -> list[WebAuthnCredentialRecord]: ...

    def upsert(self, record: WebAuthnCredentialRecord) -> WebAuthnCredentialRecord: ...


class WebAuthnChallengeRepository(Protocol):
    def create(self, record: WebAuthnChallengeRecord) -> WebAuthnChallengeRecord: ...

    def get_by_challenge(self, challenge: str) -> WebAuthnChallengeRecord | None: ...

    def consume_atomically(
        self,
        *,
        challenge: str,
        user_id: str,
        purpose: WebAuthnChallengePurpose,
        now: datetime,
    ) -> WebAuthnChallengeRecord | None: ...


class AuditLogRepository(Protocol):
    def append(self, record: AuditLogRecord) -> AuditLogRecord: ...

    def list_logs(
        self,
        *,
        target_type: AuditTargetType | None = None,
        target_id: str | None = None,
        actor_id: str | None = None,
        action: AuditAction | None = None,
    ) -> list[AuditLogRecord]: ...

    def update(self, log_id: str, **changes: Any) -> None: ...

    def delete(self, log_id: str) -> None: ...


class EvaluatorTaskRepository(Protocol):
    def get(self, task_id: str) -> EvaluatorTaskRecord | None: ...

    def list_for_evaluator(self, evaluator_id: str) -> list[EvaluatorTaskRecord]: ...

    def upsert(self, record: EvaluatorTaskRecord) -> EvaluatorTaskRecord: ...


class EvaluatorCooldownRepository(Protocol):
    def get_active_cooldown(
        self, evaluator_id: str, toilet_id: str, now: datetime
    ) -> EvaluatorCooldownRecord | None: ...

    def list_for_evaluator(
        self, evaluator_id: str
    ) -> list[EvaluatorCooldownRecord]: ...

    def upsert(self, record: EvaluatorCooldownRecord) -> EvaluatorCooldownRecord: ...


class EvaluatorInspectionRepository(Protocol):
    def get(self, inspection_id: str) -> EvaluatorInspectionRecord | None: ...

    def get_by_idempotency_key(
        self, key: str
    ) -> EvaluatorInspectionRecord | None: ...

    def list_for_evaluator(
        self, evaluator_id: str
    ) -> list[EvaluatorInspectionRecord]: ...

    def create(
        self, record: EvaluatorInspectionRecord
    ) -> EvaluatorInspectionRecord: ...


class PrivateDocumentStorageProvider(Protocol):
    def put_object(
        self,
        *,
        bucket: str,
        object_path: str,
        content: bytes,
        mime_type: str,
    ) -> None: ...

    def object_exists(self, *, bucket: str, object_path: str) -> bool: ...

    def create_signed_url(
        self,
        *,
        bucket: str,
        object_path: str,
        expires_in_seconds: int = 60,
    ) -> str: ...

    def delete_object(self, *, bucket: str, object_path: str) -> None: ...


__all__ = [
    "AuditLogRepository",
    "EvaluatorClock",
    "EvaluatorCooldownRepository",
    "EvaluatorInspectionRepository",
    "EvaluatorTaskRepository",
    "EvaluatorUserRepository",
    "EvaluatorVerificationRepository",
    "PrivateDocumentStorageProvider",
    "SystemEvaluatorClock",
    "VerificationStatus",
    "WebAuthnChallengeRepository",
    "WebAuthnCredentialRepository",
]

