"""Private Government ID Storage, Magic-Byte File Validation, Short-Lived
Admin Signed Preview URLs, and Verifiable Retention Cleanup.

OWNER: Ibrahim (ID storage & retention workflow)
COORDINATES WITH: Shabaz (Storage RLS & Security), Shubham (Verification Schema)

Enforces Condition 6:
- Private storage bucket (`evaluator-ids`) with zero public URLs.
- Strict magic-byte signature validation (`JPEG`, `PNG`, `WEBP`, `PDF`), size limit
  (`<= 5 MB`), and rejection of executables, scripts, archives, or PDF JavaScript.
- Short-lived signed URLs (`60 seconds` default, max `120 seconds`) restricted to
  verified `admin` callers and logged in `public.audit_logs`.
- Automated retention cleanup of expired raw ID objects (`now >= retention_expires_at`),
  verifying object deletion (`object_exists() == False`) before marking
  `deletion_verified = True`, `purged_at = now`, and `document_storage_path = 'PURGED'`.
- Treats retained hashes and user-linked metadata as personal data accessible only
  under strict access controls.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Any

from app.modules.evaluator.config import (
    EvaluatorModuleSettings,
    get_evaluator_module_settings,
)
from app.modules.evaluator.domain import (
    AuditLogRecord,
    EvaluatorUserRecord,
    EvaluatorVerificationRecord,
)
from app.modules.evaluator.enums import (
    AllowedIDMimeType,
    AuditAction,
    AuditTargetType,
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
from app.modules.evaluator.interfaces import (
    EvaluatorClock,
    PrivateDocumentStorageProvider,
    SystemEvaluatorClock,
)
from app.modules.evaluator.repositories import (
    EvaluatorRepositoryBundle,
    get_evaluator_repository_bundle,
)

# Forbidden executable / script signatures
FORBIDDEN_MAGIC_PREFIXES: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "Windows executable (PE)"),
    (b"\x7fELF", "Linux ELF executable"),
    (b"#!", "Shell/script executable"),
    (b"PK\x03\x04", "ZIP/APK/JAR archive"),
    (b"<svg", "SVG markup (XSS risk)"),
    (b"<?xml", "XML/SVG markup"),
    (b"<html", "HTML document"),
    (b"<!doctype html", "HTML document"),
    (b"<script", "Script payload"),
)

MIME_TO_CANONICAL_EXT: dict[AllowedIDMimeType, str] = {
    AllowedIDMimeType.JPEG: "jpg",
    AllowedIDMimeType.PNG: "png",
    AllowedIDMimeType.WEBP: "webp",
    AllowedIDMimeType.PDF: "pdf",
}


def detect_and_validate_id_magic_bytes(
    file_bytes: bytes,
    declared_mime_type: str | None = None,
    *,
    max_bytes: int = 5 * 1024 * 1024,
) -> tuple[AllowedIDMimeType, str]:
    """Inspect magic bytes of an uploaded ID document.

    Returns `(verified_mime_type, canonical_extension)` or raises `DocumentStorageError`.
    """
    if not isinstance(file_bytes, bytes) or len(file_bytes) == 0:
        raise DocumentStorageError(
            "Uploaded identity document must not be empty.",
            code="document_empty",
        )

    if len(file_bytes) > max_bytes:
        raise DocumentStorageError(
            f"Uploaded identity document ({len(file_bytes)} bytes) exceeds the "
            f"maximum allowed size ({max_bytes} bytes).",
            status_code=413,
            code="document_too_large",
        )

    head_lower = file_bytes[:64].lstrip().lower()
    for prefix, label in FORBIDDEN_MAGIC_PREFIXES:
        if file_bytes.startswith(prefix) or head_lower.startswith(prefix.lower()):
            raise DocumentStorageError(
                f"Rejected forbidden file payload: {label}.",
                code="document_forbidden_format",
            )

    detected_mime: AllowedIDMimeType | None = None
    if file_bytes.startswith(b"\xff\xd8\xff"):
        detected_mime = AllowedIDMimeType.JPEG
    elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_mime = AllowedIDMimeType.PNG
    elif len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        detected_mime = AllowedIDMimeType.WEBP
    elif file_bytes.startswith(b"%PDF-"):
        # Reject PDFs containing embedded JavaScript actions
        lowered_pdf = file_bytes.lower()
        if b"/javascript" in lowered_pdf or b"/js " in lowered_pdf or b"/js(" in lowered_pdf:
            raise DocumentStorageError(
                "PDF documents containing embedded JavaScript are forbidden.",
                code="document_pdf_javascript_forbidden",
            )
        detected_mime = AllowedIDMimeType.PDF

    if detected_mime is None:
        raise DocumentStorageError(
            "File magic bytes do not match any permitted format "
            "(image/jpeg, image/png, image/webp, application/pdf).",
            code="document_invalid_magic_bytes",
        )

    if declared_mime_type:
        norm_declared = declared_mime_type.split(";")[0].strip().lower()
        if norm_declared == "image/jpg":
            norm_declared = "image/jpeg"
        if norm_declared and norm_declared != detected_mime.value:
            raise DocumentStorageError(
                f"Declared MIME type '{declared_mime_type}' does not match "
                f"actual file signature '{detected_mime.value}'.",
                code="document_mime_mismatch",
            )

    return detected_mime, MIME_TO_CANONICAL_EXT[detected_mime]


class InMemoryPrivateDocumentStorage:
    """In-memory private bucket storage adapter for development & deterministic tests.

    Never exposes public URLs; generates short-lived token-bound signed URLs and
    supports verifiable object deletion (`object_exists() -> False`).
    """

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, tuple[bytes, str]]] = {
            "evaluator-ids": {},
            "inspection-evidence": {},
        }

    def clear(self) -> None:
        for bucket in self._buckets.values():
            bucket.clear()

    def put_object(
        self,
        *,
        bucket: str,
        object_path: str,
        content: bytes,
        mime_type: str,
    ) -> None:
        if ".." in object_path or object_path.startswith("/"):
            raise DocumentStorageError(
                "Invalid storage object path.", code="storage_invalid_path"
            )
        bucket_store = self._buckets.setdefault(bucket, {})
        bucket_store[object_path] = (content, mime_type)

    def object_exists(self, *, bucket: str, object_path: str) -> bool:
        return object_path in self._buckets.get(bucket, {})

    def create_signed_url(
        self,
        *,
        bucket: str,
        object_path: str,
        expires_in_seconds: int = 60,
    ) -> str:
        if not self.object_exists(bucket=bucket, object_path=object_path):
            raise EvaluatorNotFoundError(
                "Requested private storage object does not exist or has been purged."
            )
        if expires_in_seconds <= 0 or expires_in_seconds > 120:
            raise DocumentStorageError(
                "Signed preview URL TTL must be between 1 and 120 seconds.",
                code="storage_invalid_ttl",
            )
        token = secrets.token_urlsafe(24)
        return (
            f"https://private-storage.namma-suvidha.local/storage/v1/object/sign/"
            f"{bucket}/{object_path}?token={token}&expires_in={expires_in_seconds}"
        )

    def delete_object(self, *, bucket: str, object_path: str) -> None:
        bucket_store = self._buckets.get(bucket, {})
        bucket_store.pop(object_path, None)


_DEFAULT_STORAGE = InMemoryPrivateDocumentStorage()


def get_private_document_storage() -> InMemoryPrivateDocumentStorage:
    return _DEFAULT_STORAGE


class EvaluatorDocumentStorageService:
    """Service orchestrating private ID uploads, admin signed URL generation,
    resubmission replacement, and verifiable retention cleanup.
    """

    def __init__(
        self,
        *,
        repos: EvaluatorRepositoryBundle | None = None,
        storage: PrivateDocumentStorageProvider | None = None,
        settings: EvaluatorModuleSettings | None = None,
        clock: EvaluatorClock | None = None,
    ) -> None:
        self._repos = repos or get_evaluator_repository_bundle()
        self._storage = storage or get_private_document_storage()
        self._settings = settings or get_evaluator_module_settings()
        self._clock = clock or SystemEvaluatorClock()

    def upload_identity_document(
        self,
        evaluator: EvaluatorUserRecord,
        *,
        document_type: IDDocumentType,
        file_bytes: bytes,
        declared_mime_type: str | None = None,
    ) -> EvaluatorVerificationRecord:
        now = self._clock.now()
        if evaluator.role != UserRole.EVALUATOR:
            raise EvaluatorForbiddenError(
                "Only evaluators may upload onboarding identity documents."
            )

        if evaluator.evaluator_status not in (
            EvaluatorLifecycleStatus.PENDING,
            EvaluatorLifecycleStatus.REJECTED,
        ):
            raise EvaluatorConflictError(
                f"Cannot upload identity document when account status is "
                f"'{evaluator.evaluator_status}'.",
                code="document_upload_not_permitted",
            )

        if document_type == IDDocumentType.LEGACY_MIGRATED:
            raise DocumentStorageError(
                "document_type 'legacy_migrated' is reserved for system backfill.",
                code="document_invalid_type",
            )

        verified_mime, ext = detect_and_validate_id_magic_bytes(
            file_bytes,
            declared_mime_type=declared_mime_type,
            max_bytes=self._settings.ID_MAX_BYTES,
        )

        # If replacing a previous rejected/pending verification, schedule the old
        # verification's storage object for immediate retention purge:
        previous = self._repos.verifications.get_latest_for_evaluator(evaluator.id)
        if previous is not None and previous.purged_at is None:
            self._repos.verifications.upsert(
                previous.model_copy(
                    update={
                        "retention_expires_at": now,
                        "updated_at": now,
                    }
                )
            )

        ver_id = f"ver-{uuid.uuid4().hex[:12]}"
        app_ref = evaluator.application_reference or f"EV-2026-{uuid.uuid4().hex[:6].upper()}"
        object_path = f"{evaluator.id}/{ver_id}.{ext}"
        sha256_hex = hashlib.sha256(file_bytes).hexdigest()

        self._storage.put_object(
            bucket=self._settings.ID_STORAGE_BUCKET,
            object_path=object_path,
            content=file_bytes,
            mime_type=verified_mime.value,
        )

        record = EvaluatorVerificationRecord(
            id=ver_id,
            evaluator_id=evaluator.id,
            application_reference=app_ref,
            document_type=document_type,
            document_storage_bucket=self._settings.ID_STORAGE_BUCKET,
            document_storage_path=object_path,
            mime_type=verified_mime,
            file_size_bytes=len(file_bytes),
            sha256_checksum=sha256_hex,
            verification_status=VerificationStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        saved = self._repos.verifications.upsert(record)

        # If evaluator was previously rejected, resubmitting transitions them back to PENDING
        was_rejected = (
            evaluator.evaluator_status == EvaluatorLifecycleStatus.REJECTED
        )
        updated_user = evaluator.model_copy(
            update={
                "application_reference": app_ref,
                "evaluator_status": EvaluatorLifecycleStatus.PENDING,
                "updated_at": now,
            }
        )
        self._repos.users.upsert(updated_user)

        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=evaluator.id,
                actor_role=evaluator.role.value,
                action=(
                    AuditAction.EVALUATOR_RESUBMITTED
                    if was_rejected
                    else AuditAction.DOCUMENT_UPLOADED
                ),
                target_type=AuditTargetType.IDENTITY_DOCUMENT,
                target_id=saved.id,
                previous_status="rejected" if was_rejected else "pending",
                new_status="pending",
                metadata={
                    "verification_id": saved.id,
                    "application_reference": app_ref,
                    "document_type": document_type.value,
                    "mime_type": verified_mime.value,
                    "file_size_bytes": len(file_bytes),
                },
                created_at=now,
            )
        )
        return saved

    def generate_admin_document_preview(
        self,
        *,
        admin_user: EvaluatorUserRecord,
        evaluator_id: str,
    ) -> dict[str, Any]:
        """Generate a short-lived (60s) signed URL for an authorised admin to inspect
        an evaluator's uploaded ID document. Logs `evaluator.document_previewed`.
        """
        now = self._clock.now()
        if admin_user.role != UserRole.ADMIN:
            raise EvaluatorForbiddenError(
                "Only administrators may preview evaluator identity documents.",
                code="admin_role_required",
            )

        latest = self._repos.verifications.get_latest_for_evaluator(evaluator_id)
        if latest is None:
            raise EvaluatorNotFoundError(
                f"No identity document record found for evaluator '{evaluator_id}'."
            )

        if (
            latest.purged_at is not None
            or latest.document_storage_path == "PURGED"
            or not self._storage.object_exists(
                bucket=latest.document_storage_bucket,
                object_path=latest.document_storage_path,
            )
        ):
            raise EvaluatorNotFoundError(
                "Identity document raw file is no longer available (purged per retention policy).",
                code="document_not_available_or_purged",
            )

        ttl = min(120, max(1, self._settings.ID_SIGNED_URL_TTL_SECONDS))
        signed_url = self._storage.create_signed_url(
            bucket=latest.document_storage_bucket,
            object_path=latest.document_storage_path,
            expires_in_seconds=ttl,
        )

        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=admin_user.id,
                actor_role=admin_user.role.value,
                action=AuditAction.DOCUMENT_PREVIEWED,
                target_type=AuditTargetType.IDENTITY_DOCUMENT,
                target_id=latest.id,
                metadata={
                    "verification_id": latest.id,
                    "evaluator_id": evaluator_id,
                    "expires_in_seconds": ttl,
                },
                created_at=now,
            )
        )
        return {
            "verification_id": latest.id,
            "evaluator_id": evaluator_id,
            "document_type": latest.document_type.value,
            "mime_type": latest.mime_type.value,
            "verification_status": latest.verification_status.value,
            "signed_url": signed_url,
            "expires_in_seconds": ttl,
        }

    def purge_expired_documents(
        self,
        *,
        actor_id: str | None = None,
        actor_role: str = "system",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Execute retention cleanup on all verification records where
        `now >= retention_expires_at` and `purged_at IS NULL`.

        Verifies that `object_exists() == False` after removal before setting
        `deletion_verified = True`, `purged_at = now`, `document_storage_path = 'PURGED'`,
        and clearing legacy `users.id_document_url`.
        """
        current_time = now or self._clock.now()
        expired_rows = self._repos.verifications.list_expired_unpurged(current_time)

        purged_ids: list[str] = []
        failed_ids: list[str] = []

        for ver in expired_rows:
            bucket = ver.document_storage_bucket
            path = ver.document_storage_path
            if path and path != "PURGED":
                self._storage.delete_object(bucket=bucket, object_path=path)

            still_exists = (
                self._storage.object_exists(bucket=bucket, object_path=path)
                if path and path != "PURGED"
                else False
            )
            if still_exists:
                failed_ids.append(ver.id)
                continue

            new_ver_status = (
                VerificationStatus.EXPIRED_PURGED
                if ver.verification_status == VerificationStatus.REJECTED
                else ver.verification_status
            )
            updated_ver = ver.model_copy(
                update={
                    "document_storage_path": "PURGED",
                    "purged_at": current_time,
                    "deletion_verified": True,
                    "verification_status": new_ver_status,
                    "updated_at": current_time,
                }
            )
            self._repos.verifications.upsert(updated_ver)

            # Clear legacy `users.id_document_url` if set
            eval_user = self._repos.users.get(ver.evaluator_id)
            if eval_user is not None and eval_user.id_document_url is not None:
                self._repos.users.upsert(
                    eval_user.model_copy(
                        update={
                            "id_document_url": None,
                            "updated_at": current_time,
                        }
                    )
                )

            self._repos.audit_logs.append(
                AuditLogRecord(
                    id=f"aud-{uuid.uuid4().hex[:12]}",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action=AuditAction.DOCUMENT_PURGED,
                    target_type=AuditTargetType.IDENTITY_DOCUMENT,
                    target_id=ver.id,
                    metadata={
                        "verification_id": ver.id,
                        "evaluator_id": ver.evaluator_id,
                        "deletion_verified": True,
                    },
                    created_at=current_time,
                )
            )
            purged_ids.append(ver.id)

        return {
            "evaluated_at": current_time.isoformat(),
            "expired_found": len(expired_rows),
            "purged_count": len(purged_ids),
            "purged_verification_ids": purged_ids,
            "failed_verification_ids": failed_ids,
        }

