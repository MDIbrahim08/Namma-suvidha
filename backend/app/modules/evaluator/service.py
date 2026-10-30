"""Evaluator Onboarding, Admin Verification State Machine, Task Acceptance,
and WebAuthn-Protected Inspection Submission Services.

OWNER: Ibrahim
COORDINATES WITH: Shabaz (Auth & RLS), Shubham (45-day Cooldown & Scoring)

Enforces Condition 5, 6, 7 & 8:
- Explicit evaluator lifecycle state machine:
  * `pending -> approved` (requires uploaded pending ID document)
  * `pending -> rejected` (requires explicit `reason`)
  * `rejected -> pending` (when evaluator resubmits corrected document)
  * `approved -> suspended` (requires explicit `reason`)
  * `suspended -> approved` (requires explicit `reason`)
- Inspects Shubham's 45-day cooldown (`evaluator_cooldowns`) without duplicating
  allocation algorithms.
- Requires a cryptographically verified WebAuthn assertion (`purpose='inspection_submit'`)
  bound to `task_id` before any inspection submission is saved.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from app.modules.evaluator.config import (
    EvaluatorModuleSettings,
    get_evaluator_module_settings,
)
from app.modules.evaluator.domain import (
    AuditLogRecord,
    EvaluatorCooldownRecord,
    EvaluatorInspectionRecord,
    EvaluatorTaskRecord,
    EvaluatorUserRecord,
    EvaluatorVerificationRecord,
)
from app.modules.evaluator.enums import (
    AuditAction,
    AuditTargetType,
    EvaluatorLifecycleStatus,
    EvaluatorTaskStatus,
    UserRole,
    VerificationStatus,
    WebAuthnChallengePurpose,
)
from app.modules.evaluator.exceptions import (
    EvaluatorConflictError,
    EvaluatorForbiddenError,
    EvaluatorNotApprovedError,
    EvaluatorNotFoundError,
    EvaluatorValidationError,
    IllegalEvaluatorStateTransitionError,
)
from app.modules.evaluator.interfaces import EvaluatorClock, SystemEvaluatorClock
from app.modules.evaluator.repositories import (
    EvaluatorRepositoryBundle,
    get_evaluator_repository_bundle,
)
from app.modules.evaluator.webauthn import WebAuthnService


def _require_non_empty_reason(reason: str | None, action_label: str) -> str:
    cleaned = (reason or "").strip()
    if len(cleaned) < 3:
        raise EvaluatorValidationError(
            f"A reason (at least 3 characters) is mandatory when performing '{action_label}'.",
            code="transition_reason_required",
        )
    return cleaned


class EvaluatorOnboardingService:
    """Handles gig-worker evaluator profile registration, onboarding status checks,
    task acceptance, and WebAuthn-authenticated inspection submission.
    """

    def __init__(
        self,
        *,
        repos: EvaluatorRepositoryBundle | None = None,
        webauthn: WebAuthnService | None = None,
        settings: EvaluatorModuleSettings | None = None,
        clock: EvaluatorClock | None = None,
    ) -> None:
        self._repos = repos or get_evaluator_repository_bundle()
        self._settings = settings or get_evaluator_module_settings()
        self._clock = clock or SystemEvaluatorClock()
        self._webauthn = webauthn or WebAuthnService(
            repos=self._repos, settings=self._settings, clock=self._clock
        )

    def register_or_update_profile(
        self,
        *,
        user_id: str,
        email: str,
        full_name: str,
        phone: str,
        operating_area: str,
        preferred_language: str = "en",
    ) -> EvaluatorUserRecord:
        now = self._clock.now()
        clean_name = full_name.strip()
        clean_phone = phone.strip()
        clean_area = operating_area.strip()
        if len(clean_name) < 2:
            raise EvaluatorValidationError("full_name must be at least 2 characters.")
        if len(clean_phone) < 8:
            raise EvaluatorValidationError("phone must be a valid phone number.")
        if len(clean_area) < 2:
            raise EvaluatorValidationError(
                "operating_area (city/zone/ward) is required."
            )

        existing = self._repos.users.get(user_id)
        if existing is not None:
            if existing.role != UserRole.EVALUATOR:
                raise EvaluatorForbiddenError(
                    f"Account already holds role '{existing.role.value}' and cannot "
                    "register as an evaluator."
                )
            if existing.evaluator_status == EvaluatorLifecycleStatus.SUSPENDED:
                raise EvaluatorForbiddenError(
                    "Suspended evaluator accounts cannot modify onboarding registration.",
                    code="evaluator_suspended",
                )
            app_ref = (
                existing.application_reference
                or f"EV-2026-{uuid.uuid4().hex[:6].upper()}"
            )
            updated = existing.model_copy(
                update={
                    "full_name": clean_name,
                    "phone": clean_phone,
                    "operating_area": clean_area,
                    "preferred_language": preferred_language.strip() or "en",
                    "application_reference": app_ref,
                    "updated_at": now,
                }
            )
            return self._repos.users.upsert(updated)

        app_ref = f"EV-2026-{uuid.uuid4().hex[:6].upper()}"
        new_user = EvaluatorUserRecord(
            id=user_id,
            full_name=clean_name,
            email=email.strip().lower(),
            phone=clean_phone,
            role=UserRole.EVALUATOR,
            evaluator_status=EvaluatorLifecycleStatus.PENDING,
            operating_area=clean_area,
            preferred_language=preferred_language.strip() or "en",
            application_reference=app_ref,
            email_verified_at=now,
            wallet_balance=0.0,
            created_at=now,
            updated_at=now,
        )
        saved = self._repos.users.upsert(new_user)
        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=saved.id,
                actor_role=saved.role.value,
                action=AuditAction.EVALUATOR_REGISTERED,
                target_type=AuditTargetType.EVALUATOR_ACCOUNT,
                target_id=saved.id,
                previous_status=None,
                new_status=EvaluatorLifecycleStatus.PENDING.value,
                metadata={
                    "application_reference": app_ref,
                    "operating_area": clean_area,
                },
                created_at=now,
            )
        )
        return saved

    def get_onboarding_status(self, user: EvaluatorUserRecord) -> dict[str, Any]:
        latest_ver = self._repos.verifications.get_latest_for_evaluator(user.id)
        active_passkeys = self._repos.credentials.list_for_user(
            user.id, active_only=True
        )
        is_approved = (
            user.evaluator_status == EvaluatorLifecycleStatus.APPROVED
        )
        can_inspect = is_approved and len(active_passkeys) > 0

        return {
            "evaluator_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "operating_area": user.operating_area,
            "preferred_language": user.preferred_language,
            "application_reference": user.application_reference,
            "evaluator_status": (
                user.evaluator_status.value if user.evaluator_status else "pending"
            ),
            "status_reason": user.status_reason,
            "status_updated_at": (
                user.status_updated_at.isoformat()
                if user.status_updated_at
                else None
            ),
            "email_verified": user.email_verified_at is not None,
            "document_uploaded": latest_ver is not None,
            "document_verification_status": (
                latest_ver.verification_status.value if latest_ver else None
            ),
            "document_type": (
                latest_ver.document_type.value if latest_ver else None
            ),
            "document_rejection_reason": (
                latest_ver.rejection_reason if latest_ver else None
            ),
            "passkey_registered": len(active_passkeys) > 0,
            "active_passkey_count": len(active_passkeys),
            "passkeys": [
                {
                    "id": pk.id,
                    "credential_id": pk.credential_id,
                    "device_name": pk.device_name,
                    "transports": pk.transports,
                    "created_at": pk.created_at.isoformat(),
                    "last_used_at": (
                        pk.last_used_at.isoformat() if pk.last_used_at else None
                    ),
                }
                for pk in active_passkeys
            ],
            "inspection_access_granted": can_inspect,
        }

    def list_assigned_tasks(
        self, evaluator: EvaluatorUserRecord
    ) -> list[EvaluatorTaskRecord]:
        if evaluator.evaluator_status != EvaluatorLifecycleStatus.APPROVED:
            raise EvaluatorNotApprovedError(
                "Only approved evaluators may view or execute assigned inspection tasks."
            )
        return self._repos.tasks.list_for_evaluator(evaluator.id)

    def accept_task(
        self, evaluator: EvaluatorUserRecord, task_id: str
    ) -> EvaluatorTaskRecord:
        now = self._clock.now()
        if evaluator.evaluator_status != EvaluatorLifecycleStatus.APPROVED:
            raise EvaluatorNotApprovedError(
                "Only approved evaluators may accept inspection tasks."
            )

        task = self._repos.tasks.get(task_id)
        if task is None:
            raise EvaluatorNotFoundError(f"Task '{task_id}' not found.")
        if task.evaluator_id != evaluator.id:
            raise EvaluatorForbiddenError(
                "Cannot accept an inspection task assigned to another evaluator."
            )

        cooldown = self._repos.cooldowns.get_active_cooldown(
            evaluator.id, task.toilet_id, now
        )
        if cooldown is not None:
            raise EvaluatorConflictError(
                f"45-day evaluator-toilet cooldown is active until "
                f"{cooldown.cooldown_until.isoformat()}.",
                code="evaluator_cooldown_active",
            )

        if task.status != EvaluatorTaskStatus.ASSIGNED:
            raise EvaluatorConflictError(
                f"Task '{task_id}' cannot be accepted from status '{task.status.value}'."
            )

        updated = task.model_copy(
            update={"status": EvaluatorTaskStatus.IN_PROGRESS}
        )
        saved = self._repos.tasks.upsert(updated)
        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=evaluator.id,
                actor_role=evaluator.role.value,
                action=AuditAction.TASK_ACCEPTED,
                target_type=AuditTargetType.EVALUATOR_TASK,
                target_id=task.id,
                previous_status=EvaluatorTaskStatus.ASSIGNED.value,
                new_status=EvaluatorTaskStatus.IN_PROGRESS.value,
                metadata={
                    "task_id": task.id,
                    "toilet_id": task.toilet_id,
                },
                created_at=now,
            )
        )
        return saved

    def submit_inspection_with_webauthn(
        self,
        evaluator: EvaluatorUserRecord,
        *,
        task_id: str,
        checklist_answers: dict[str, Any],
        evidence_urls: list[str] | None = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
        credential_id: str | None = None,
        client_data_json_b64: str | None = None,
        authenticator_data_b64: str | None = None,
        signature_b64: str | None = None,
    ) -> EvaluatorInspectionRecord:
        now = self._clock.now()
        if evaluator.evaluator_status != EvaluatorLifecycleStatus.APPROVED:
            raise EvaluatorNotApprovedError(
                "Only approved evaluators may submit washroom inspections."
            )

        # Idempotency check before consuming challenge if already submitted
        if idempotency_key:
            existing_insp = self._repos.inspections.get_by_idempotency_key(
                idempotency_key
            )
            if existing_insp is not None:
                if existing_insp.evaluator_id != evaluator.id:
                    raise EvaluatorForbiddenError("Idempotency key collision.")
                return existing_insp

        task = self._repos.tasks.get(task_id)
        if task is None:
            raise EvaluatorNotFoundError(f"Task '{task_id}' not found.")
        if task.evaluator_id != evaluator.id:
            raise EvaluatorForbiddenError(
                "Task is not assigned to the authenticated evaluator."
            )
        if task.status == EvaluatorTaskStatus.COMPLETED:
            raise EvaluatorConflictError(
                f"Task '{task_id}' has already been completed.",
                code="task_already_completed",
            )

        cooldown = self._repos.cooldowns.get_active_cooldown(
            evaluator.id, task.toilet_id, now
        )
        if cooldown is not None:
            raise EvaluatorConflictError(
                f"45-day evaluator-toilet cooldown is active for facility "
                f"'{task.toilet_id}' until {cooldown.cooldown_until.isoformat()}.",
                code="evaluator_cooldown_active",
            )

        # Cryptographically verify WebAuthn assertion bound to `inspection_submit` and `task_id`
        verified_cred, consumed_chal = self._webauthn.verify_assertion(
            evaluator,
            credential_id=credential_id,
            client_data_json_b64=client_data_json_b64,
            authenticator_data_b64=authenticator_data_b64,
            signature_b64=signature_b64,
            purpose=WebAuthnChallengePurpose.INSPECTION_SUBMIT,
            expected_operation_context={"task_id": task_id},
        )

        insp_id = f"insp-{uuid.uuid4().hex[:12]}"
        insp_rec = EvaluatorInspectionRecord(
            id=insp_id,
            task_id=task.id,
            toilet_id=task.toilet_id,
            evaluator_id=evaluator.id,
            checklist_answers=checklist_answers,
            evidence_urls=evidence_urls or [],
            notes=notes,
            submission_idempotency_key=idempotency_key,
            webauthn_credential_id_used=verified_cred.credential_id,
            webauthn_challenge_id=consumed_chal.id,
            submitted_at=now,
        )
        saved_insp = self._repos.inspections.create(insp_rec)

        # Mark task completed and record Shubham's 45-day cooldown window
        self._repos.tasks.upsert(
            task.model_copy(
                update={
                    "status": EvaluatorTaskStatus.COMPLETED,
                    "completed_at": now,
                }
            )
        )
        self._repos.cooldowns.upsert(
            EvaluatorCooldownRecord(
                id=f"cd-{uuid.uuid4().hex[:12]}",
                evaluator_id=evaluator.id,
                toilet_id=task.toilet_id,
                last_inspected_at=now,
                cooldown_until=now + timedelta(days=45),
            )
        )

        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=evaluator.id,
                actor_role=evaluator.role.value,
                action=AuditAction.INSPECTION_SUBMITTED,
                target_type=AuditTargetType.INSPECTION,
                target_id=saved_insp.id,
                metadata={
                    "inspection_id": saved_insp.id,
                    "task_id": task.id,
                    "toilet_id": task.toilet_id,
                    "challenge_id": consumed_chal.id,
                    "idempotency_key": idempotency_key,
                },
                created_at=now,
            )
        )
        return saved_insp


class AdminEvaluatorManagementService:
    """Handles administrative evaluator review, approval, rejection, suspension,
    reinstatement, and audit log querying.
    """

    def __init__(
        self,
        *,
        repos: EvaluatorRepositoryBundle | None = None,
        settings: EvaluatorModuleSettings | None = None,
        clock: EvaluatorClock | None = None,
    ) -> None:
        self._repos = repos or get_evaluator_repository_bundle()
        self._settings = settings or get_evaluator_module_settings()
        self._clock = clock or SystemEvaluatorClock()

    def _require_admin(self, admin: EvaluatorUserRecord) -> None:
        if admin.role != UserRole.ADMIN:
            raise EvaluatorForbiddenError(
                "Administrator role is required.", code="admin_role_required"
            )

    def _get_evaluator(self, evaluator_id: str) -> EvaluatorUserRecord:
        user = self._repos.users.get(evaluator_id)
        if user is None or user.role != UserRole.EVALUATOR:
            raise EvaluatorNotFoundError(
                f"Evaluator '{evaluator_id}' not found."
            )
        return user

    def list_applications(
        self,
        admin: EvaluatorUserRecord,
        *,
        status: EvaluatorLifecycleStatus | None = None,
        operating_area: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        self._require_admin(admin)
        users = self._repos.users.list_evaluators(
            status=status, operating_area=operating_area, search=search
        )
        items: list[dict[str, Any]] = []
        for u in users:
            ver = self._repos.verifications.get_latest_for_evaluator(u.id)
            passkeys = self._repos.credentials.list_for_user(
                u.id, active_only=True
            )
            items.append(
                {
                    "evaluator_id": u.id,
                    "full_name": u.full_name,
                    "email": u.email,
                    "phone": u.phone,
                    "operating_area": u.operating_area,
                    "application_reference": u.application_reference,
                    "evaluator_status": (
                        u.evaluator_status.value if u.evaluator_status else "pending"
                    ),
                    "document_type": ver.document_type.value if ver else None,
                    "verification_status": (
                        ver.verification_status.value if ver else None
                    ),
                    "active_passkey_count": len(passkeys),
                    "created_at": u.created_at.isoformat(),
                    "status_updated_at": (
                        u.status_updated_at.isoformat()
                        if u.status_updated_at
                        else None
                    ),
                }
            )
        return items

    def get_evaluator_detail(
        self, admin: EvaluatorUserRecord, evaluator_id: str
    ) -> dict[str, Any]:
        self._require_admin(admin)
        u = self._get_evaluator(evaluator_id)
        ver = self._repos.verifications.get_latest_for_evaluator(u.id)
        passkeys = self._repos.credentials.list_for_user(
            u.id, active_only=False
        )
        audit_entries = self._repos.audit_logs.list_logs(target_id=u.id)

        return {
            "evaluator_id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "phone": u.phone,
            "operating_area": u.operating_area,
            "preferred_language": u.preferred_language,
            "application_reference": u.application_reference,
            "evaluator_status": (
                u.evaluator_status.value if u.evaluator_status else "pending"
            ),
            "status_reason": u.status_reason,
            "status_updated_by": u.status_updated_by,
            "status_updated_at": (
                u.status_updated_at.isoformat()
                if u.status_updated_at
                else None
            ),
            "email_verified": u.email_verified_at is not None,
            "latest_verification": (
                {
                    "verification_id": ver.id,
                    "document_type": ver.document_type.value,
                    "mime_type": ver.mime_type.value,
                    "file_size_bytes": ver.file_size_bytes,
                    "verification_status": ver.verification_status.value,
                    "reviewed_by": ver.reviewed_by,
                    "reviewed_at": (
                        ver.reviewed_at.isoformat() if ver.reviewed_at else None
                    ),
                    "rejection_reason": ver.rejection_reason,
                    "retention_expires_at": (
                        ver.retention_expires_at.isoformat()
                        if ver.retention_expires_at
                        else None
                    ),
                    "purged_at": (
                        ver.purged_at.isoformat() if ver.purged_at else None
                    ),
                    "deletion_verified": ver.deletion_verified,
                }
                if ver
                else None
            ),
            "passkeys": [
                {
                    "id": pk.id,
                    "credential_id": pk.credential_id,
                    "device_name": pk.device_name,
                    "transports": pk.transports,
                    "sign_count": pk.sign_count,
                    "migration_source": pk.migration_source.value,
                    "created_at": pk.created_at.isoformat(),
                    "last_used_at": (
                        pk.last_used_at.isoformat() if pk.last_used_at else None
                    ),
                    "revoked_at": (
                        pk.revoked_at.isoformat() if pk.revoked_at else None
                    ),
                }
                for pk in passkeys
            ],
            "audit_trail": [
                {
                    "id": a.id,
                    "actor_id": a.actor_id,
                    "actor_role": a.actor_role,
                    "action": a.action.value,
                    "previous_status": a.previous_status,
                    "new_status": a.new_status,
                    "reason": a.reason,
                    "created_at": a.created_at.isoformat(),
                }
                for a in audit_entries
            ],
        }

    def approve_evaluator(
        self,
        admin: EvaluatorUserRecord,
        evaluator_id: str,
        *,
        note: str | None = None,
    ) -> EvaluatorUserRecord:
        """Transition `pending -> approved` and schedule 7-day ID retention expiry."""
        self._require_admin(admin)
        now = self._clock.now()
        u = self._get_evaluator(evaluator_id)

        if u.evaluator_status != EvaluatorLifecycleStatus.PENDING:
            raise IllegalEvaluatorStateTransitionError(
                f"Cannot approve evaluator from status '{u.evaluator_status}'. "
                "Only 'pending' evaluators can be approved."
            )

        ver: EvaluatorVerificationRecord | None = (
            self._repos.verifications.get_latest_for_evaluator(u.id)
        )
        if ver is None:
            raise EvaluatorConflictError(
                "Cannot approve evaluator before a government identity document "
                "has been uploaded.",
                code="identity_document_required_for_approval",
            )

        retention_days = max(0, self._settings.ID_RETENTION_DAYS_AFTER_DECISION)
        approved_ver = ver.model_copy(
            update={
                "verification_status": VerificationStatus.APPROVED,
                "reviewed_by": admin.id,
                "reviewed_at": now,
                "rejection_reason": None,
                "retention_expires_at": now + timedelta(days=retention_days),
                "updated_at": now,
            }
        )
        self._repos.verifications.upsert(approved_ver)

        updated_user = u.model_copy(
            update={
                "evaluator_status": EvaluatorLifecycleStatus.APPROVED,
                "status_updated_by": admin.id,
                "status_updated_at": now,
                "status_reason": (note or "Approved after identity verification").strip(),
                "updated_at": now,
            }
        )
        saved_user = self._repos.users.upsert(updated_user)

        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=admin.id,
                actor_role=admin.role.value,
                action=AuditAction.EVALUATOR_APPROVED,
                target_type=AuditTargetType.EVALUATOR_ACCOUNT,
                target_id=u.id,
                previous_status=EvaluatorLifecycleStatus.PENDING.value,
                new_status=EvaluatorLifecycleStatus.APPROVED.value,
                reason=saved_user.status_reason,
                metadata={
                    "application_reference": u.application_reference,
                    "verification_id": ver.id,
                },
                created_at=now,
            )
        )
        return saved_user

    def reject_evaluator(
        self,
        admin: EvaluatorUserRecord,
        evaluator_id: str,
        *,
        reason: str,
    ) -> EvaluatorUserRecord:
        """Transition `pending -> rejected` with mandatory reason and 7-day retention expiry."""
        self._require_admin(admin)
        clean_reason = _require_non_empty_reason(reason, "reject_evaluator")
        now = self._clock.now()
        u = self._get_evaluator(evaluator_id)

        if u.evaluator_status != EvaluatorLifecycleStatus.PENDING:
            raise IllegalEvaluatorStateTransitionError(
                f"Cannot reject evaluator from status '{u.evaluator_status}'. "
                "Only 'pending' evaluators can be rejected."
            )

        ver = self._repos.verifications.get_latest_for_evaluator(u.id)
        if ver is not None:
            retention_days = max(0, self._settings.ID_RETENTION_DAYS_AFTER_DECISION)
            self._repos.verifications.upsert(
                ver.model_copy(
                    update={
                        "verification_status": VerificationStatus.REJECTED,
                        "reviewed_by": admin.id,
                        "reviewed_at": now,
                        "rejection_reason": clean_reason,
                        "retention_expires_at": now
                        + timedelta(days=retention_days),
                        "updated_at": now,
                    }
                )
            )

        updated_user = u.model_copy(
            update={
                "evaluator_status": EvaluatorLifecycleStatus.REJECTED,
                "status_updated_by": admin.id,
                "status_updated_at": now,
                "status_reason": clean_reason,
                "updated_at": now,
            }
        )
        saved_user = self._repos.users.upsert(updated_user)

        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=admin.id,
                actor_role=admin.role.value,
                action=AuditAction.EVALUATOR_REJECTED,
                target_type=AuditTargetType.EVALUATOR_ACCOUNT,
                target_id=u.id,
                previous_status=EvaluatorLifecycleStatus.PENDING.value,
                new_status=EvaluatorLifecycleStatus.REJECTED.value,
                reason=clean_reason,
                metadata={
                    "application_reference": u.application_reference,
                    "verification_id": ver.id if ver else None,
                },
                created_at=now,
            )
        )
        return saved_user

    def suspend_evaluator(
        self,
        admin: EvaluatorUserRecord,
        evaluator_id: str,
        *,
        reason: str,
    ) -> EvaluatorUserRecord:
        """Transition `approved -> suspended` with mandatory reason."""
        self._require_admin(admin)
        clean_reason = _require_non_empty_reason(reason, "suspend_evaluator")
        now = self._clock.now()
        u = self._get_evaluator(evaluator_id)

        if u.evaluator_status != EvaluatorLifecycleStatus.APPROVED:
            raise IllegalEvaluatorStateTransitionError(
                f"Cannot suspend evaluator from status '{u.evaluator_status}'. "
                "Only 'approved' evaluators can be suspended."
            )

        updated_user = u.model_copy(
            update={
                "evaluator_status": EvaluatorLifecycleStatus.SUSPENDED,
                "status_updated_by": admin.id,
                "status_updated_at": now,
                "status_reason": clean_reason,
                "updated_at": now,
            }
        )
        saved_user = self._repos.users.upsert(updated_user)

        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=admin.id,
                actor_role=admin.role.value,
                action=AuditAction.EVALUATOR_SUSPENDED,
                target_type=AuditTargetType.EVALUATOR_ACCOUNT,
                target_id=u.id,
                previous_status=EvaluatorLifecycleStatus.APPROVED.value,
                new_status=EvaluatorLifecycleStatus.SUSPENDED.value,
                reason=clean_reason,
                metadata={"application_reference": u.application_reference},
                created_at=now,
            )
        )
        return saved_user

    def reinstate_evaluator(
        self,
        admin: EvaluatorUserRecord,
        evaluator_id: str,
        *,
        reason: str,
    ) -> EvaluatorUserRecord:
        """Transition `suspended -> approved` with mandatory reason."""
        self._require_admin(admin)
        clean_reason = _require_non_empty_reason(reason, "reinstate_evaluator")
        now = self._clock.now()
        u = self._get_evaluator(evaluator_id)

        if u.evaluator_status != EvaluatorLifecycleStatus.SUSPENDED:
            raise IllegalEvaluatorStateTransitionError(
                f"Cannot reinstate evaluator from status '{u.evaluator_status}'. "
                "Only 'suspended' evaluators can be reinstated."
            )

        updated_user = u.model_copy(
            update={
                "evaluator_status": EvaluatorLifecycleStatus.APPROVED,
                "status_updated_by": admin.id,
                "status_updated_at": now,
                "status_reason": clean_reason,
                "updated_at": now,
            }
        )
        saved_user = self._repos.users.upsert(updated_user)

        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=admin.id,
                actor_role=admin.role.value,
                action=AuditAction.EVALUATOR_REINSTATED,
                target_type=AuditTargetType.EVALUATOR_ACCOUNT,
                target_id=u.id,
                previous_status=EvaluatorLifecycleStatus.SUSPENDED.value,
                new_status=EvaluatorLifecycleStatus.APPROVED.value,
                reason=clean_reason,
                metadata={"application_reference": u.application_reference},
                created_at=now,
            )
        )
        return saved_user

