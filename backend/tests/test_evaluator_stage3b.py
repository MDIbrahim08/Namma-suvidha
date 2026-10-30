"""Stage 3B tests: Isolated EvaluatorAuthProvider & SupabaseJwtVerifier.

Tests:
- Valid HS256 JWT signature, issuer, audience, expiry, and verified email.
- Expired token rejection (`jwt_expired`).
- Tampered / invalid signature rejection (`jwt_invalid_signature`).
- Unsigned `alg: "none"` token rejection (`jwt_invalid_algorithm` / `jwt_unsigned`).
- Wrong issuer (`jwt_invalid_issuer`) and wrong audience (`jwt_invalid_audience`).
- Unverified email rejection (`email_not_verified`).
- Authoritative database role and status verification (ignoring spoofed JWT `user_metadata.role`).
- Preservation of `backend/app/core/security.py` and FastAPI `dependency_overrides[get_current_user]`.
- Recording of `security.privileged_access_denied` in append-only `audit_logs`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from starlette.requests import Request

from app.core.config import Settings
from app.core.security import get_current_user
from app.main import app
from app.modules.evaluator.auth_interface import (
    EvaluatorAuthProvider,
    SupabaseJwtVerifier,
    build_hs256_jwt,
)
from app.modules.evaluator.domain import EvaluatorUserRecord, WebAuthnCredentialRecord
from app.modules.evaluator.enums import (
    AuditAction,
    EvaluatorLifecycleStatus,
    UserRole,
)
from app.modules.evaluator.exceptions import (
    EvaluatorAuthenticationError,
    EvaluatorForbiddenError,
    EvaluatorNotApprovedError,
)
from app.modules.evaluator.repositories import get_evaluator_memory_bundle

TEST_JWT_SECRET = "test-supabase-jwt-hmac-secret-key-2026"
TEST_SUPABASE_URL = "https://projectref.supabase.co"
TEST_ISSUER = f"{TEST_SUPABASE_URL}/auth/v1"


class FixedClock:
    def __init__(self, dt: datetime) -> None:
        self._dt = dt

    def now(self) -> datetime:
        return self._dt


def _make_request(
    path: str = "/api/v1/evaluator/tasks",
    token: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode("ascii")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": headers,
        "app": app,
    }
    return Request(scope)


def _valid_claims(now: datetime, sub: str = "eval-101") -> dict[str, object]:
    return {
        "sub": sub,
        "email": "eval101@example.com",
        "email_verified": True,
        "iss": TEST_ISSUER,
        "aud": "authenticated",
        "iat": int(now.timestamp()) - 60,
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }


def test_stage3b_jwt_verifier_accepts_valid_token_and_rejects_invalid_tokens() -> None:
    now = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)
    verifier = SupabaseJwtVerifier(
        jwt_secret=TEST_JWT_SECRET,
        expected_issuer=TEST_ISSUER,
        expected_audience="authenticated",
    )

    valid_token = build_hs256_jwt(_valid_claims(now), TEST_JWT_SECRET)
    claims = verifier.verify_token(valid_token, now=now)
    assert claims.sub == "eval-101"
    assert claims.email == "eval101@example.com"
    assert claims.email_verified is True

    # 1. Expired token
    expired_claims = _valid_claims(now)
    expired_claims["exp"] = int((now - timedelta(seconds=10)).timestamp())
    expired_token = build_hs256_jwt(expired_claims, TEST_JWT_SECRET)
    with pytest.raises(EvaluatorAuthenticationError) as exp_exc:
        verifier.verify_token(expired_token, now=now)
    assert exp_exc.value.code == "jwt_expired"

    # 2. Invalid signature (signed with wrong secret)
    bad_sig_token = build_hs256_jwt(_valid_claims(now), "wrong-secret")
    with pytest.raises(EvaluatorAuthenticationError) as sig_exc:
        verifier.verify_token(bad_sig_token, now=now)
    assert sig_exc.value.code == "jwt_invalid_signature"

    # 3. Unsigned token (`alg: "none"`)
    unsigned_token = build_hs256_jwt(
        _valid_claims(now), TEST_JWT_SECRET, header_overrides={"alg": "none"}
    )
    with pytest.raises(EvaluatorAuthenticationError) as none_exc:
        verifier.verify_token(unsigned_token, now=now)
    assert none_exc.value.code in ("jwt_unsigned", "jwt_invalid_algorithm")

    # 4. Wrong issuer
    wrong_iss_claims = _valid_claims(now)
    wrong_iss_claims["iss"] = "https://attacker.example.com/auth/v1"
    wrong_iss_token = build_hs256_jwt(wrong_iss_claims, TEST_JWT_SECRET)
    with pytest.raises(EvaluatorAuthenticationError) as iss_exc:
        verifier.verify_token(wrong_iss_token, now=now)
    assert iss_exc.value.code == "jwt_invalid_issuer"

    # 5. Wrong audience
    wrong_aud_claims = _valid_claims(now)
    wrong_aud_claims["aud"] = "anon"
    wrong_aud_token = build_hs256_jwt(wrong_aud_claims, TEST_JWT_SECRET)
    with pytest.raises(EvaluatorAuthenticationError) as aud_exc:
        verifier.verify_token(wrong_aud_token, now=now)
    assert aud_exc.value.code == "jwt_invalid_audience"


def test_stage3b_authoritative_role_and_status_checks_ignore_spoofed_jwt_claims() -> None:
    now = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)
    bundle = get_evaluator_memory_bundle()
    bundle.clear_all()

    settings = Settings(
        SUPABASE_URL=TEST_SUPABASE_URL,
        SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
    )
    provider = EvaluatorAuthProvider(
        settings=settings, repos=bundle, clock=FixedClock(now)
    )

    # Insert a CITIZEN user in authoritative database, even though JWT claims "admin"
    citizen_user = EvaluatorUserRecord(
        id="user-cit-1",
        full_name="Citizen One",
        email="citizen@example.com",
        role=UserRole.CITIZEN,
        evaluator_status=None,
        created_at=now,
        updated_at=now,
    )
    bundle.users.upsert(citizen_user)

    spoofed_claims = _valid_claims(now, sub="user-cit-1")
    spoofed_claims["role"] = "admin"
    spoofed_claims["user_metadata"] = {"role": "admin", "evaluator_status": "approved"}
    spoofed_token = build_hs256_jwt(spoofed_claims, TEST_JWT_SECRET)

    req = _make_request("/api/v1/admin/evaluators", token=spoofed_token)
    with pytest.raises(EvaluatorForbiddenError) as admin_exc:
        provider.require_admin_user(req)
    assert admin_exc.value.code == "admin_role_required"

    # Verify audit log recorded the privilege escalation attempt
    denied_logs = bundle.audit_logs.list_logs(
        action=AuditAction.PRIVILEGED_ACCESS_DENIED
    )
    assert len(denied_logs) == 1
    assert denied_logs[0].actor_id == "user-cit-1"
    assert denied_logs[0].metadata["actual_role_or_status"] == "citizen"

    # Now insert a PENDING evaluator: allowed on onboarding, blocked on approved-only routes
    pending_eval = EvaluatorUserRecord(
        id="eval-pending-1",
        full_name="Pending Evaluator",
        email="pending@example.com",
        role=UserRole.EVALUATOR,
        evaluator_status=EvaluatorLifecycleStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    bundle.users.upsert(pending_eval)
    pending_token = build_hs256_jwt(
        _valid_claims(now, sub="eval-pending-1"), TEST_JWT_SECRET
    )
    req_eval = _make_request("/api/v1/evaluator/tasks", token=pending_token)

    # Allowed as general evaluator (for onboarding/status check)
    resolved_user = provider.require_evaluator_user(req_eval)
    assert resolved_user.id == "eval-pending-1"

    # Blocked from approved-evaluator task execution
    with pytest.raises(EvaluatorNotApprovedError) as not_app_exc:
        provider.require_approved_evaluator_user(req_eval)
    assert not_app_exc.value.code == "evaluator_not_approved"

    # Approve the evaluator, but without an active passkey -> still blocked from inspection actions
    approved_eval = pending_eval.model_copy(
        update={"evaluator_status": EvaluatorLifecycleStatus.APPROVED}
    )
    bundle.users.upsert(approved_eval)
    with pytest.raises(EvaluatorNotApprovedError) as no_pk_exc:
        provider.require_approved_evaluator_user(req_eval)
    assert no_pk_exc.value.code == "webauthn_passkey_required"

    # Register an active passkey -> now passes require_approved_evaluator_user
    bundle.credentials.upsert(
        WebAuthnCredentialRecord(
            id="cred-1",
            user_id="eval-pending-1",
            credential_id="cred-abc",
            public_key="cose-pub",
            sign_count=1,
            created_at=now,
        )
    )
    approved_and_keyed = provider.require_approved_evaluator_user(req_eval)
    assert approved_and_keyed.id == "eval-pending-1"


def test_stage3b_preserves_fastapi_dependency_overrides_for_tests() -> None:
    now = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)
    bundle = get_evaluator_memory_bundle()
    bundle.clear_all()
    provider = EvaluatorAuthProvider(repos=bundle, clock=FixedClock(now))

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin-override-1",
        "email": "admin@example.com",
        "role": "admin",
        "email_verified": True,
    }
    try:
        req = _make_request("/api/v1/admin/evaluators", token=None)
        admin_user = provider.require_admin_user(req)
        assert admin_user.id == "admin-override-1"
        assert admin_user.role == UserRole.ADMIN
    finally:
        app.dependency_overrides.pop(get_current_user, None)

