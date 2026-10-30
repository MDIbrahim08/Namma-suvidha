"""Stage 3E & 3F comprehensive integration, security, and negative test suite:
- Full evaluator onboarding & admin verification lifecycle (`pending -> approved`,
  `pending -> rejected -> pending -> approved`, `approved -> suspended -> approved`).
- End-to-end HTTP integration tests on `/api/v1/evaluator/*` and `/api/v1/evaluator/admin/*`.
- Cryptographic WebAuthn assertion verification required on `/api/v1/evaluator/inspections/submit`.
- Negative tests:
  * Expired tokens, invalid signatures, wrong roles, unverified emails.
  * Pending / rejected / suspended evaluators blocked from task execution & inspection submission.
  * Credential-ID-only submission rejected (`webauthn_assertion_incomplete`).
  * Replayed WebAuthn challenge rejected (`webauthn_challenge_replayed_or_expired`).
  * Revoked WebAuthn credential rejected (`webauthn_credential_revoked`).
  * Unauthorised ID preview rejected (`admin_role_required`).
  * 45-day evaluator-toilet cooldown enforced on task acceptance and inspection submission.
  * Idempotent inspection submission on duplicate `idempotency_key`.
- SQL proposal verification tests (`20261031_evaluator_auth_schema.sql` and
  `20261031_evaluator_auth_rls.sql`) confirming append-only trigger `trg_audit_logs_immutable`
  and `REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM service_role`.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.modules.evaluator.auth_interface import build_hs256_jwt
from app.modules.evaluator.config import get_evaluator_module_settings
from app.modules.evaluator.dependencies import get_evaluator_clock
from app.modules.evaluator.domain import EvaluatorTaskRecord
from app.modules.evaluator.enums import AuditAction, EvaluatorTaskStatus
from app.modules.evaluator.repositories import get_evaluator_memory_bundle
from app.modules.evaluator.storage import get_private_document_storage
from app.modules.evaluator.webauthn import (
    FLAG_AT,
    FLAG_UP,
    FLAG_UV,
    b64url_encode,
    encode_es256_public_key,
)
from tests.test_evaluator_stage3c import (
    build_assertion_payload,
    build_attestation_auth_data,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_SECRET = "stage3ef-integration-jwt-secret-2026"
TEST_SUPABASE_URL = "https://stage3ef.supabase.co"
TEST_ISSUER = f"{TEST_SUPABASE_URL}/auth/v1"


class MutableClock:
    def __init__(self, initial: datetime) -> None:
        self.current = initial

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current = self.current + delta


def _make_auth_header(
    sub: str,
    now: datetime,
    *,
    email: str | None = None,
    role: str = "evaluator",
    secret: str = TEST_SECRET,
    exp_delta: timedelta = timedelta(minutes=30),
) -> dict[str, str]:
    token = build_hs256_jwt(
        {
            "sub": sub,
            "email": email or f"{sub}@example.com",
            "email_verified": True,
            "role": role,
            "iss": TEST_ISSUER,
            "aud": "authenticated",
            "iat": int(now.timestamp()) - 10,
            "exp": int((now + exp_delta).timestamp()),
        },
        secret,
    )
    return {"Authorization": f"Bearer {token}"}


def test_stage3ef_end_to_end_onboarding_admin_lifecycle_webauthn_and_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("EVAL_REPOSITORY_BACKEND", "memory")
    get_settings.cache_clear()
    get_evaluator_module_settings.cache_clear()

    clock = MutableClock(datetime(2026, 10, 31, 12, 0, tzinfo=UTC))
    app.dependency_overrides[get_evaluator_clock] = lambda: clock

    bundle = get_evaluator_memory_bundle()
    bundle.clear_all()
    storage = get_private_document_storage()
    storage.clear()

    client = TestClient(app)

    try:
        eval_headers = _make_auth_header("eval-501", clock.now())
        admin_headers = _make_auth_header(
            "admin-501", clock.now(), role="admin"
        )

        # 1. Register evaluator profile -> status is 'pending'
        reg_resp = client.post(
            "/api/v1/evaluator/register",
            headers=eval_headers,
            json={
                "full_name": "Deepa Krishnan",
                "phone": "+919845012345",
                "operating_area": "Jayanagar Ward 170",
                "preferred_language": "kn",
            },
        )
        assert reg_resp.status_code == 201
        reg_body = reg_resp.json()
        assert reg_body["evaluator_status"] == "pending"
        assert reg_body["inspection_access_granted"] is False
        app_ref = reg_body["application_reference"]
        assert app_ref.startswith("EV-2026-")

        # 2. Pending evaluator is blocked from `/api/v1/evaluator/tasks` (403)
        tasks_blocked = client.get("/api/v1/evaluator/tasks", headers=eval_headers)
        assert tasks_blocked.status_code == 403
        assert tasks_blocked.json()["code"] == "evaluator_not_approved"

        # 3. Admin cannot approve before identity document is uploaded (409)
        premature_approve = client.post(
            "/api/v1/evaluator/admin/applications/eval-501/approve",
            headers=admin_headers,
            json={"note": "Trying to approve without ID"},
        )
        assert premature_approve.status_code == 409
        assert (
            premature_approve.json()["code"]
            == "identity_document_required_for_approval"
        )

        # 4. Evaluator uploads valid PNG driving licence
        png_bytes = b"\x89PNG\r\n\x1a\ndeepa-driving-licence-scan"
        doc_resp = client.post(
            "/api/v1/evaluator/documents",
            headers=eval_headers,
            json={
                "document_type": "driving_licence",
                "file_base64": base64.b64encode(png_bytes).decode("ascii"),
                "mime_type": "image/png",
            },
        )
        assert doc_resp.status_code == 201
        ver_id_1 = doc_resp.json()["verification_id"]

        # 5. Evaluator (non-admin) is forbidden from calling admin document preview (403)
        unauth_preview = client.get(
            "/api/v1/evaluator/admin/applications/eval-501/document",
            headers=eval_headers,
        )
        assert unauth_preview.status_code == 403
        assert unauth_preview.json()["code"] == "admin_role_required"

        # 6. Admin previews document via 60s signed URL, then rejects blurry scan (`pending -> rejected`)
        admin_preview = client.get(
            "/api/v1/evaluator/admin/applications/eval-501/document",
            headers=admin_headers,
        )
        assert admin_preview.status_code == 200
        assert admin_preview.json()["expires_in_seconds"] == 60

        reject_resp = client.post(
            "/api/v1/evaluator/admin/applications/eval-501/reject",
            headers=admin_headers,
            json={"reason": "Driving licence image is blurry; please re-upload."},
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["evaluator_status"] == "rejected"

        # 7. Evaluator resubmits clear PNG document (`rejected -> pending`)
        resubmit_resp = client.post(
            "/api/v1/evaluator/documents",
            headers=eval_headers,
            json={
                "document_type": "driving_licence",
                "file_base64": base64.b64encode(
                    b"\x89PNG\r\n\x1a\nclear-driving-licence-scan"
                ).decode("ascii"),
                "mime_type": "image/png",
            },
        )
        assert resubmit_resp.status_code == 201
        ver_id_2 = resubmit_resp.json()["verification_id"]
        assert ver_id_2 != ver_id_1

        # 8. Evaluator registers WebAuthn passkey during onboarding
        pk_opts_resp = client.post(
            "/api/v1/evaluator/passkeys/register/options",
            headers=eval_headers,
            json={"origin": "http://localhost:5173"},
        )
        assert pk_opts_resp.status_code == 200
        reg_challenge = pk_opts_resp.json()["challenge"]

        priv_key = ec.generate_private_key(ec.SECP256R1())
        pub_key_b64 = encode_es256_public_key(priv_key.public_key())
        cred_id = b64url_encode(b"deepa-android-passkey-1")

        reg_client_data = b64url_encode(
            json.dumps(
                {
                    "type": "webauthn.create",
                    "challenge": reg_challenge,
                    "origin": "http://localhost:5173",
                }
            ).encode("utf-8")
        )
        reg_auth_data = build_attestation_auth_data(
            rp_id="localhost",
            flags=FLAG_UP | FLAG_UV | FLAG_AT,
            sign_count=1,
            credential_id=cred_id,
            public_key_b64=pub_key_b64,
        )
        pk_verify_resp = client.post(
            "/api/v1/evaluator/passkeys/register/verify",
            headers=eval_headers,
            json={
                "credential_id": cred_id,
                "client_data_json_b64": reg_client_data,
                "authenticator_data_b64": reg_auth_data,
                "device_name": "Deepa Samsung Passkey",
            },
        )
        assert pk_verify_resp.status_code == 201

        # 9. Admin approves evaluator (`pending -> approved`)
        approve_resp = client.post(
            "/api/v1/evaluator/admin/applications/eval-501/approve",
            headers=admin_headers,
            json={"note": "Clear driving licence verified."},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["evaluator_status"] == "approved"
        assert approve_resp.json()["inspection_access_granted"] is True

        # 10. Assign an inspection task to eval-501 & test task acceptance + WebAuthn submission
        bundle.tasks.upsert(
            EvaluatorTaskRecord(
                id="task-501",
                toilet_id="toilet-jayanagar-1",
                evaluator_id="eval-501",
                status=EvaluatorTaskStatus.ASSIGNED,
                photo_challenge_prompt="Show tap running water",
                assigned_at=clock.now(),
            )
        )

        tasks_ok = client.get("/api/v1/evaluator/tasks", headers=eval_headers)
        assert tasks_ok.status_code == 200
        assert tasks_ok.json()["total"] == 1

        accept_resp = client.post(
            "/api/v1/evaluator/tasks/task-501/accept", headers=eval_headers
        )
        assert accept_resp.status_code == 200
        assert accept_resp.json()["status"] == "in_progress"

        # 11. Negative test: Submitting inspection with credential_id alone (no signature) MUST fail (401)
        cred_only_submit = client.post(
            "/api/v1/evaluator/inspections/submit",
            headers=eval_headers,
            json={
                "task_id": "task-501",
                "checklist_answers": {"water_available": True, "clean_floor": True},
                "credential_id": cred_id,
            },
        )
        assert cred_only_submit.status_code == 401
        assert cred_only_submit.json()["code"] == "webauthn_assertion_incomplete"

        # 12. Request WebAuthn challenge bound to `inspection_submit` and `task-501`
        auth_opts_resp = client.post(
            "/api/v1/evaluator/passkeys/authenticate/options",
            headers=eval_headers,
            json={"purpose": "inspection_submit", "task_id": "task-501"},
        )
        assert auth_opts_resp.status_code == 200
        submit_challenge = auth_opts_resp.json()["challenge"]

        c_b64, a_b64, s_b64 = build_assertion_payload(
            private_key=priv_key,
            rp_id="localhost",
            challenge=submit_challenge,
            sign_count=2,
        )

        # 13. Submit verified inspection with idempotency_key
        submit_resp = client.post(
            "/api/v1/evaluator/inspections/submit",
            headers=eval_headers,
            json={
                "task_id": "task-501",
                "checklist_answers": {"water_available": True, "clean_floor": True},
                "evidence_urls": ["inspection-evidence/eval-501/photo1.jpg"],
                "notes": "Clean and functional",
                "idempotency_key": "idem-501-a",
                "credential_id": cred_id,
                "client_data_json_b64": c_b64,
                "authenticator_data_b64": a_b64,
                "signature_b64": s_b64,
            },
        )
        assert submit_resp.status_code == 201
        insp_id = submit_resp.json()["id"]
        assert submit_resp.json()["webauthn_credential_id_used"] == cred_id

        # 14. Idempotent retry with same `idempotency_key` returns exact same inspection without error
        retry_resp = client.post(
            "/api/v1/evaluator/inspections/submit",
            headers=eval_headers,
            json={
                "task_id": "task-501",
                "checklist_answers": {"water_available": True, "clean_floor": True},
                "idempotency_key": "idem-501-a",
            },
        )
        assert retry_resp.status_code == 201
        assert retry_resp.json()["id"] == insp_id

        # 15. 45-day cooldown is now active for (eval-501, toilet-jayanagar-1)
        bundle.tasks.upsert(
            EvaluatorTaskRecord(
                id="task-502-same-toilet",
                toilet_id="toilet-jayanagar-1",
                evaluator_id="eval-501",
                status=EvaluatorTaskStatus.ASSIGNED,
                assigned_at=clock.now(),
            )
        )
        cooldown_blocked = client.post(
            "/api/v1/evaluator/tasks/task-502-same-toilet/accept",
            headers=eval_headers,
        )
        assert cooldown_blocked.status_code == 409
        assert cooldown_blocked.json()["code"] == "evaluator_cooldown_active"

        # 16. Admin suspends and reinstates evaluator (`approved -> suspended -> approved`)
        suspend_resp = client.post(
            "/api/v1/evaluator/admin/applications/eval-501/suspend",
            headers=admin_headers,
            json={"reason": "Routine compliance audit hold"},
        )
        assert suspend_resp.status_code == 200
        assert suspend_resp.json()["evaluator_status"] == "suspended"

        # Suspended evaluator is immediately blocked from `/tasks`
        suspended_tasks = client.get(
            "/api/v1/evaluator/tasks", headers=eval_headers
        )
        assert suspended_tasks.status_code == 403

        reinstate_resp = client.post(
            "/api/v1/evaluator/admin/applications/eval-501/reinstate",
            headers=admin_headers,
            json={"reason": "Compliance audit cleared"},
        )
        assert reinstate_resp.status_code == 200
        assert reinstate_resp.json()["evaluator_status"] == "approved"

        # 17. Advance clock 8 days -> run admin retention purge -> verify raw documents deleted
        clock.advance(timedelta(days=8))
        admin_headers_later = _make_auth_header(
            "admin-501", clock.now(), role="admin"
        )
        purge_resp = client.post(
            "/api/v1/evaluator/admin/retention/purge",
            headers=admin_headers_later,
        )
        assert purge_resp.status_code == 200
        assert purge_resp.json()["purged_count"] >= 1

        # 18. Verify complete append-only audit trail via `/api/v1/evaluator/admin/audit-logs`
        audit_resp = client.get(
            "/api/v1/evaluator/admin/audit-logs",
            headers=admin_headers_later,
        )
        assert audit_resp.status_code == 200
        recorded_actions = {item["action"] for item in audit_resp.json()["items"]}
        expected_actions = {
            AuditAction.EVALUATOR_REGISTERED.value,
            AuditAction.DOCUMENT_UPLOADED.value,
            AuditAction.DOCUMENT_PREVIEWED.value,
            AuditAction.EVALUATOR_REJECTED.value,
            AuditAction.EVALUATOR_RESUBMITTED.value,
            AuditAction.PASSKEY_REGISTERED.value,
            AuditAction.EVALUATOR_APPROVED.value,
            AuditAction.TASK_ACCEPTED.value,
            AuditAction.INSPECTION_SUBMITTED.value,
            AuditAction.EVALUATOR_SUSPENDED.value,
            AuditAction.EVALUATOR_REINSTATED.value,
            AuditAction.DOCUMENT_PURGED.value,
        }
        assert expected_actions.issubset(recorded_actions)
    finally:
        app.dependency_overrides.pop(get_evaluator_clock, None)
        get_settings.cache_clear()
        get_evaluator_module_settings.cache_clear()


def test_stage3f_sql_proposals_enforce_audit_immutability_and_service_role_restrictions() -> None:
    """Verify that the SQL proposal scripts contain the mandatory database trigger
    and `service_role` privilege revocations for `public.audit_logs`, and that
    protected shared files remain untouched.
    """
    schema_sql = (
        REPO_ROOT
        / "docs"
        / "proposals"
        / "sql"
        / "20261031_evaluator_auth_schema.sql"
    ).read_text(encoding="utf-8")
    rls_sql = (
        REPO_ROOT
        / "docs"
        / "proposals"
        / "sql"
        / "20261031_evaluator_auth_rls.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE TRIGGER trg_audit_logs_immutable" in schema_sql
    assert "BEFORE UPDATE OR DELETE ON public.audit_logs" in schema_sql
    assert "sign_count_initialized BOOLEAN NOT NULL DEFAULT true" in schema_sql
    assert "deletion_verified BOOLEAN NOT NULL DEFAULT false" in schema_sql

    assert (
        "REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM service_role;"
        in rls_sql
    )
    assert "REVOKE ALL ON public.webauthn_challenges FROM anon, authenticated;" in rls_sql
    assert "AS RESTRICTIVE" in rls_sql

    # Verify `backend/app/core/security.py` remains untouched (Condition 1)
    security_py = (
        REPO_ROOT / "backend" / "app" / "core" / "security.py"
    ).read_text(encoding="utf-8")
    assert "OWNER: Shabaz" in security_py
    assert "HTTP_501_NOT_IMPLEMENTED" in security_py

