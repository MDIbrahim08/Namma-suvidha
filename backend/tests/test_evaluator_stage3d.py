"""Stage 3D tests: Private Government ID storage, magic-byte validation,
short-lived admin signed preview URLs, unauthorised access prevention,
and verifiable retention cleanup.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.evaluator.domain import EvaluatorUserRecord
from app.modules.evaluator.enums import (
    AllowedIDMimeType,
    AuditAction,
    EvaluatorLifecycleStatus,
    IDDocumentType,
    UserRole,
    VerificationStatus,
)
from app.modules.evaluator.exceptions import (
    DocumentStorageError,
    EvaluatorConflictError,
    EvaluatorForbiddenError,
    EvaluatorNotFoundError,
)
from app.modules.evaluator.repositories import get_evaluator_memory_bundle
from app.modules.evaluator.storage import (
    EvaluatorDocumentStorageService,
    InMemoryPrivateDocumentStorage,
    detect_and_validate_id_magic_bytes,
)


class FixedClock:
    def __init__(self, dt: datetime) -> None:
        self._dt = dt

    def now(self) -> datetime:
        return self._dt


def test_stage3d_magic_byte_validation_accepts_valid_and_rejects_malicious_payloads() -> None:
    # Valid PNG
    png_mime, png_ext = detect_and_validate_id_magic_bytes(
        b"\x89PNG\r\n\x1a\nvalid-png-data", "image/png"
    )
    assert png_mime == AllowedIDMimeType.PNG
    assert png_ext == "png"

    # Valid JPEG
    jpg_mime, jpg_ext = detect_and_validate_id_magic_bytes(
        b"\xff\xd8\xff\xe0valid-jpeg", "image/jpeg"
    )
    assert jpg_mime == AllowedIDMimeType.JPEG
    assert jpg_ext == "jpg"

    # Valid PDF (without JavaScript)
    pdf_mime, pdf_ext = detect_and_validate_id_magic_bytes(
        b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj", "application/pdf"
    )
    assert pdf_mime == AllowedIDMimeType.PDF
    assert pdf_ext == "pdf"

    # Reject empty payload
    with pytest.raises(DocumentStorageError) as empty_exc:
        detect_and_validate_id_magic_bytes(b"")
    assert empty_exc.value.code == "document_empty"

    # Reject oversized payload
    with pytest.raises(DocumentStorageError) as size_exc:
        detect_and_validate_id_magic_bytes(
            b"\x89PNG\r\n\x1a\n" + b"x" * 2048, max_bytes=1024
        )
    assert size_exc.value.code == "document_too_large"
    assert size_exc.value.status_code == 413

    # Reject Windows EXE disguised as PNG
    with pytest.raises(DocumentStorageError) as exe_exc:
        detect_and_validate_id_magic_bytes(b"MZ\x90\x00\x03\x00", "image/png")
    assert exe_exc.value.code == "document_forbidden_format"

    # Reject SVG XSS disguised as PNG
    with pytest.raises(DocumentStorageError) as svg_exc:
        detect_and_validate_id_magic_bytes(
            b"<svg onload='alert(1)'></svg>", "image/png"
        )
    assert svg_exc.value.code == "document_forbidden_format"

    # Reject PDF with embedded JavaScript
    with pytest.raises(DocumentStorageError) as pdf_js_exc:
        detect_and_validate_id_magic_bytes(
            b"%PDF-1.7\n<< /S /JavaScript /JS (app.alert(1)) >>",
            "application/pdf",
        )
    assert pdf_js_exc.value.code == "document_pdf_javascript_forbidden"

    # Reject MIME mismatch (PNG magic bytes declared as PDF)
    with pytest.raises(DocumentStorageError) as mime_exc:
        detect_and_validate_id_magic_bytes(
            b"\x89PNG\r\n\x1a\nbody", "application/pdf"
        )
    assert mime_exc.value.code == "document_mime_mismatch"


def test_stage3d_private_id_upload_admin_signed_preview_and_verifiable_retention_purge() -> None:
    now = datetime(2026, 10, 31, 11, 0, tzinfo=UTC)
    bundle = get_evaluator_memory_bundle()
    bundle.clear_all()
    storage = InMemoryPrivateDocumentStorage()
    storage.clear()

    svc = EvaluatorDocumentStorageService(
        repos=bundle, storage=storage, clock=FixedClock(now)
    )

    eval_user = EvaluatorUserRecord(
        id="eval-301",
        full_name="Meera Nair",
        email="meera@example.com",
        role=UserRole.EVALUATOR,
        evaluator_status=EvaluatorLifecycleStatus.PENDING,
        application_reference="EV-2026-MEERA1",
        id_document_url="legacy-placeholder-ref",
        created_at=now,
        updated_at=now,
    )
    bundle.users.upsert(eval_user)

    admin_user = EvaluatorUserRecord(
        id="admin-301",
        full_name="Admin Reviewer",
        email="admin@example.com",
        role=UserRole.ADMIN,
        evaluator_status=None,
        created_at=now,
        updated_at=now,
    )
    bundle.users.upsert(admin_user)

    # 1. Evaluator uploads valid PNG driving licence
    ver_rec = svc.upload_identity_document(
        eval_user,
        document_type=IDDocumentType.DRIVING_LICENCE,
        file_bytes=b"\x89PNG\r\n\x1a\ndriving-licence-bytes",
        declared_mime_type="image/png",
    )
    assert ver_rec.evaluator_id == "eval-301"
    assert ver_rec.document_storage_bucket == "evaluator-ids"
    assert ver_rec.document_storage_path.startswith("eval-301/ver-")
    assert ver_rec.document_storage_path.endswith(".png")
    assert storage.object_exists(
        bucket="evaluator-ids", object_path=ver_rec.document_storage_path
    )

    # 2. Non-admin (including the evaluator herself or a government user) CANNOT generate preview URL
    with pytest.raises(EvaluatorForbiddenError):
        svc.generate_admin_document_preview(
            admin_user=eval_user, evaluator_id="eval-301"
        )

    # 3. Admin generates short-lived 60s signed URL and audit log is recorded
    preview = svc.generate_admin_document_preview(
        admin_user=admin_user, evaluator_id="eval-301"
    )
    assert preview["expires_in_seconds"] == 60
    assert "token=" in preview["signed_url"]
    preview_logs = bundle.audit_logs.list_logs(
        action=AuditAction.DOCUMENT_PREVIEWED
    )
    assert len(preview_logs) == 1
    assert preview_logs[0].actor_id == "admin-301"

    # 4. Approved evaluator cannot re-upload an ID document
    approved_eval = eval_user.model_copy(
        update={"evaluator_status": EvaluatorLifecycleStatus.APPROVED}
    )
    bundle.users.upsert(approved_eval)
    with pytest.raises(EvaluatorConflictError) as up_exc:
        svc.upload_identity_document(
            approved_eval,
            document_type=IDDocumentType.VOTER_ID,
            file_bytes=b"\x89PNG\r\n\x1a\nvoter-id",
        )
    assert up_exc.value.code == "document_upload_not_permitted"

    # 5. Simulate decision + 7-day retention expiry -> verifiable purge
    approved_ver = ver_rec.model_copy(
        update={
            "verification_status": VerificationStatus.APPROVED,
            "reviewed_by": "admin-301",
            "reviewed_at": now,
            "retention_expires_at": now + timedelta(days=7),
        }
    )
    bundle.verifications.upsert(approved_ver)

    # Before 7 days: purge finds 0 expired records
    early_purge = svc.purge_expired_documents(now=now + timedelta(days=6))
    assert early_purge["purged_count"] == 0
    assert storage.object_exists(
        bucket="evaluator-ids", object_path=ver_rec.document_storage_path
    )

    # After 7 days: purge deletes object from storage, verifies 404, marks deletion_verified=True
    late_time = now + timedelta(days=7, seconds=1)
    purge_summary = svc.purge_expired_documents(
        actor_id="admin-301", actor_role="admin", now=late_time
    )
    assert purge_summary["purged_count"] == 1
    assert ver_rec.id in purge_summary["purged_verification_ids"]

    # Confirm raw file is gone from private bucket
    assert not storage.object_exists(
        bucket="evaluator-ids", object_path=ver_rec.document_storage_path
    )

    # Confirm metadata row has deletion_verified=True, purged_at set, and storage path scrubbed
    purged_row = bundle.verifications.get(ver_rec.id)
    assert purged_row is not None
    assert purged_row.deletion_verified is True
    assert purged_row.purged_at == late_time
    assert purged_row.document_storage_path == "PURGED"

    # Confirm legacy `users.id_document_url` was also cleared
    updated_user = bundle.users.get("eval-301")
    assert updated_user is not None
    assert updated_user.id_document_url is None

    # Subsequent admin preview attempt returns 404 document_not_available_or_purged
    with pytest.raises(EvaluatorNotFoundError) as gone_exc:
        svc.generate_admin_document_preview(
            admin_user=admin_user, evaluator_id="eval-301"
        )
    assert gone_exc.value.code == "document_not_available_or_purged"

