"""Evaluator Authentication, Onboarding, WebAuthn, Inspection Submission,
and Admin Verification API routes (`/api/v1/evaluator`).

OWNER: Ibrahim (integration) + Shabaz (auth/biometrics)
"""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, status

from app.modules.evaluator.auth_interface import VerifiedJwtClaims
from app.modules.evaluator.dependencies import (
    EvaluatorServices,
    get_evaluator_services,
    require_admin,
    require_approved_evaluator,
    require_authenticated_claims,
    require_evaluator,
)
from app.modules.evaluator.domain import EvaluatorUserRecord
from app.modules.evaluator.enums import (
    AuditAction,
    AuditTargetType,
    EvaluatorLifecycleStatus,
)
from app.modules.evaluator.exceptions import DocumentStorageError
from app.schemas.evaluator import (
    AdminApproveEvaluatorRequest,
    AdminReasonRequiredRequest,
    EvaluatorDocumentBase64UploadRequest,
    EvaluatorInspectionSubmitRequest,
    EvaluatorPasskeyAuthOptionsRequest,
    EvaluatorPasskeyAuthVerifyRequest,
    EvaluatorPasskeyRegisterOptionsRequest,
    EvaluatorPasskeyRegisterVerifyRequest,
    EvaluatorRegisterRequest,
)

router = APIRouter(prefix="/evaluator", tags=["evaluator"])


# ---------------------------------------------------------------------------
# 1. Evaluator Onboarding & Status Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_evaluator_profile(
    body: EvaluatorRegisterRequest,
    claims: VerifiedJwtClaims = Depends(require_authenticated_claims),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    user = services.onboarding.register_or_update_profile(
        user_id=claims.sub,
        email=claims.email or f"{claims.sub}@example.com",
        full_name=body.full_name,
        phone=body.phone,
        operating_area=body.operating_area,
        preferred_language=body.preferred_language,
    )
    return services.onboarding.get_onboarding_status(user)


@router.get("/me")
def get_my_evaluator_status(
    evaluator: EvaluatorUserRecord = Depends(require_evaluator),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    return services.onboarding.get_onboarding_status(evaluator)


@router.post("/documents", status_code=status.HTTP_201_CREATED)
def upload_evaluator_identity_document(
    body: EvaluatorDocumentBase64UploadRequest,
    evaluator: EvaluatorUserRecord = Depends(require_evaluator),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    try:
        raw_bytes = base64.b64decode(body.file_base64, validate=True)
    except Exception as exc:
        raise DocumentStorageError(
            "file_base64 is not valid base64 encoding.",
            code="document_invalid_base64",
        ) from exc

    ver = services.documents.upload_identity_document(
        evaluator,
        document_type=body.document_type,
        file_bytes=raw_bytes,
        declared_mime_type=body.mime_type,
    )
    return {
        "verification_id": ver.id,
        "evaluator_id": ver.evaluator_id,
        "application_reference": ver.application_reference,
        "document_type": ver.document_type.value,
        "mime_type": ver.mime_type.value,
        "file_size_bytes": ver.file_size_bytes,
        "verification_status": ver.verification_status.value,
        "created_at": ver.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# 2. WebAuthn Passkey Registration, Authentication & Revocation
# ---------------------------------------------------------------------------


@router.post("/passkeys/register/options")
def get_passkey_registration_options(
    body: EvaluatorPasskeyRegisterOptionsRequest | None = Body(default=None),
    evaluator: EvaluatorUserRecord = Depends(require_evaluator),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    req = body or EvaluatorPasskeyRegisterOptionsRequest()
    return services.webauthn.generate_registration_options(
        evaluator, origin=req.origin
    )


@router.post("/passkeys/register/verify", status_code=status.HTTP_201_CREATED)
def verify_passkey_registration(
    body: EvaluatorPasskeyRegisterVerifyRequest,
    evaluator: EvaluatorUserRecord = Depends(require_evaluator),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    saved = services.webauthn.verify_registration(
        evaluator,
        credential_id=body.credential_id,
        client_data_json_b64=body.client_data_json_b64,
        authenticator_data_b64=body.authenticator_data_b64,
        public_key_b64=body.public_key_b64,
        transports=body.transports,
        device_name=body.device_name,
    )
    return {
        "id": saved.id,
        "credential_id": saved.credential_id,
        "device_name": saved.device_name,
        "transports": saved.transports,
        "sign_count": saved.sign_count,
        "created_at": saved.created_at.isoformat(),
    }


@router.post("/passkeys/authenticate/options")
def get_passkey_authentication_options(
    body: EvaluatorPasskeyAuthOptionsRequest | None = Body(default=None),
    evaluator: EvaluatorUserRecord = Depends(require_evaluator),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    req = body or EvaluatorPasskeyAuthOptionsRequest()
    op_ctx = {"task_id": req.task_id} if req.task_id else {}
    return services.webauthn.generate_authentication_options(
        evaluator,
        purpose=req.purpose,
        operation_context=op_ctx,
        origin=req.origin,
    )


@router.post("/passkeys/authenticate/verify")
def verify_passkey_authentication(
    body: EvaluatorPasskeyAuthVerifyRequest,
    evaluator: EvaluatorUserRecord = Depends(require_evaluator),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    expected_ctx = {"task_id": body.task_id} if body.task_id else None
    cred, chal = services.webauthn.verify_assertion(
        evaluator,
        credential_id=body.credential_id,
        client_data_json_b64=body.client_data_json_b64,
        authenticator_data_b64=body.authenticator_data_b64,
        signature_b64=body.signature_b64,
        purpose=body.purpose,
        expected_operation_context=expected_ctx,
    )
    return {
        "verified": True,
        "credential_id": cred.credential_id,
        "sign_count": cred.sign_count,
        "challenge_id": chal.id,
        "purpose": chal.purpose.value,
    }


@router.delete("/passkeys/{credential_id}")
def revoke_my_passkey(
    credential_id: str,
    evaluator: EvaluatorUserRecord = Depends(require_evaluator),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    revoked = services.webauthn.revoke_credential(
        actor=evaluator,
        credential_id_or_row_id=credential_id,
        reason="Revoked by evaluator",
    )
    return {
        "id": revoked.id,
        "credential_id": revoked.credential_id,
        "revoked_at": (
            revoked.revoked_at.isoformat() if revoked.revoked_at else None
        ),
    }


# ---------------------------------------------------------------------------
# 3. Approved Evaluator Task Execution & WebAuthn Inspection Submission
# ---------------------------------------------------------------------------


@router.get("/tasks")
def list_my_assigned_tasks(
    evaluator: EvaluatorUserRecord = Depends(require_approved_evaluator),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    tasks = services.onboarding.list_assigned_tasks(evaluator)
    return {
        "items": [t.model_dump(mode="json") for t in tasks],
        "total": len(tasks),
    }


@router.post("/tasks/{task_id}/accept")
def accept_assigned_task(
    task_id: str,
    evaluator: EvaluatorUserRecord = Depends(require_approved_evaluator),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    task = services.onboarding.accept_task(evaluator, task_id)
    return task.model_dump(mode="json")


@router.post("/inspections/submit", status_code=status.HTTP_201_CREATED)
def submit_verified_inspection(
    body: EvaluatorInspectionSubmitRequest,
    evaluator: EvaluatorUserRecord = Depends(require_approved_evaluator),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    insp = services.onboarding.submit_inspection_with_webauthn(
        evaluator,
        task_id=body.task_id,
        checklist_answers=body.checklist_answers,
        evidence_urls=body.evidence_urls,
        notes=body.notes,
        idempotency_key=body.idempotency_key,
        credential_id=body.credential_id,
        client_data_json_b64=body.client_data_json_b64,
        authenticator_data_b64=body.authenticator_data_b64,
        signature_b64=body.signature_b64,
    )
    return insp.model_dump(mode="json")


# ---------------------------------------------------------------------------
# 4. Admin Evaluator Verification, Lifecycle & Audit Log Endpoints
# ---------------------------------------------------------------------------


@router.get("/admin/applications")
def admin_list_evaluator_applications(
    status: EvaluatorLifecycleStatus | None = None,
    operating_area: str | None = None,
    search: str | None = None,
    admin: EvaluatorUserRecord = Depends(require_admin),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    items = services.admin.list_applications(
        admin, status=status, operating_area=operating_area, search=search
    )
    return {"items": items, "total": len(items)}


@router.get("/admin/applications/{evaluator_id}")
def admin_get_evaluator_detail(
    evaluator_id: str,
    admin: EvaluatorUserRecord = Depends(require_admin),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    return services.admin.get_evaluator_detail(admin, evaluator_id)


@router.get("/admin/applications/{evaluator_id}/document")
def admin_preview_evaluator_document(
    evaluator_id: str,
    admin: EvaluatorUserRecord = Depends(require_admin),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    return services.documents.generate_admin_document_preview(
        admin_user=admin, evaluator_id=evaluator_id
    )


@router.post("/admin/applications/{evaluator_id}/approve")
def admin_approve_evaluator(
    evaluator_id: str,
    body: AdminApproveEvaluatorRequest | None = Body(default=None),
    admin: EvaluatorUserRecord = Depends(require_admin),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    req = body or AdminApproveEvaluatorRequest()
    updated = services.admin.approve_evaluator(
        admin, evaluator_id, note=req.note
    )
    return services.onboarding.get_onboarding_status(updated)


@router.post("/admin/applications/{evaluator_id}/reject")
def admin_reject_evaluator(
    evaluator_id: str,
    body: AdminReasonRequiredRequest,
    admin: EvaluatorUserRecord = Depends(require_admin),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    updated = services.admin.reject_evaluator(
        admin, evaluator_id, reason=body.reason
    )
    return services.onboarding.get_onboarding_status(updated)


@router.post("/admin/applications/{evaluator_id}/suspend")
def admin_suspend_evaluator(
    evaluator_id: str,
    body: AdminReasonRequiredRequest,
    admin: EvaluatorUserRecord = Depends(require_admin),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    updated = services.admin.suspend_evaluator(
        admin, evaluator_id, reason=body.reason
    )
    return services.onboarding.get_onboarding_status(updated)


@router.post("/admin/applications/{evaluator_id}/reinstate")
def admin_reinstate_evaluator(
    evaluator_id: str,
    body: AdminReasonRequiredRequest,
    admin: EvaluatorUserRecord = Depends(require_admin),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    updated = services.admin.reinstate_evaluator(
        admin, evaluator_id, reason=body.reason
    )
    return services.onboarding.get_onboarding_status(updated)


@router.post("/admin/retention/purge")
def admin_run_document_retention_purge(
    admin: EvaluatorUserRecord = Depends(require_admin),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    return services.documents.purge_expired_documents(
        actor_id=admin.id, actor_role=admin.role.value
    )


@router.get("/admin/audit-logs")
def admin_list_audit_logs(
    target_type: AuditTargetType | None = Query(default=None),
    target_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    action: AuditAction | None = Query(default=None),
    admin: EvaluatorUserRecord = Depends(require_admin),
    services: EvaluatorServices = Depends(get_evaluator_services),
) -> dict[str, Any]:
    _ = admin
    logs = services.repos.audit_logs.list_logs(
        target_type=target_type,
        target_id=target_id,
        actor_id=actor_id,
        action=action,
    )
    return {
        "items": [log.model_dump(mode="json") for log in logs],
        "total": len(logs),
    }
