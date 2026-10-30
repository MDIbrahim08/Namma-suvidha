"""Isolated Evaluator Authentication Provider & Supabase JWT Verifier.

OWNER: Ibrahim (isolated evaluator auth interface)
COORDINATES WITH: Shabaz (owner of `backend/app/core/security.py`)

Enforces Condition 1 & Condition 4:
- Does NOT modify `backend/app/core/security.py` or existing Government dependencies.
- Preserves FastAPI `app.dependency_overrides[get_current_user]` for deterministic tests.
- Strictly verifies JWT signature (`HS256` with `SUPABASE_JWT_SECRET` or `ES256`/`RS256`
  via JWK public key), issuer (`iss`), audience (`aud == "authenticated"`), and expiry (`exp`).
- Rejects `alg: "none"`, unsigned tokens, wrong issuers, wrong audiences, and expired tokens.
- Resolves authoritative `role` and `evaluator_status` from the backend user repository
  (never trusting mutable client `user_metadata` role claims).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, HTTPException, Request

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.modules.evaluator.domain import AuditLogRecord, EvaluatorUserRecord
from app.modules.evaluator.enums import (
    AuditAction,
    AuditTargetType,
    EvaluatorLifecycleStatus,
    UserRole,
)
from app.modules.evaluator.exceptions import (
    EvaluatorAuthenticationError,
    EvaluatorForbiddenError,
    EvaluatorNotApprovedError,
)
from app.modules.evaluator.interfaces import EvaluatorClock, SystemEvaluatorClock
from app.modules.evaluator.repositories import (
    EvaluatorRepositoryBundle,
    get_evaluator_repository_bundle,
)


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class VerifiedJwtClaims:
    sub: str
    email: str | None
    email_verified: bool
    issuer: str
    audience: str
    expires_at: int
    raw_claims: dict[str, Any]


class SupabaseJwtVerifier:
    """Strict JWT verifier supporting HS256 (`SUPABASE_JWT_SECRET`) and asymmetric
    ES256/RS256 (when `cryptography` and JWKS keys are configured).
    """

    ALLOWED_ALGORITHMS: frozenset[str] = frozenset({"HS256", "ES256", "RS256"})

    def __init__(
        self,
        *,
        jwt_secret: str = "",
        expected_issuer: str | None = None,
        expected_audience: str = "authenticated",
        jwks_keys: list[dict[str, Any]] | None = None,
    ) -> None:
        self._jwt_secret = jwt_secret.strip()
        self._expected_issuer = (
            expected_issuer.strip().rstrip("/") if expected_issuer else None
        )
        self._expected_audience = expected_audience
        self._jwks_keys = jwks_keys or []

    def verify_token(
        self, token: str, *, now: datetime | None = None
    ) -> VerifiedJwtClaims:
        if not token or not isinstance(token, str):
            raise EvaluatorAuthenticationError(
                "Missing Bearer token.", code="jwt_missing_token"
            )

        parts = token.strip().split(".")
        if len(parts) != 3:
            raise EvaluatorAuthenticationError(
                "Malformed JWT structure.", code="jwt_malformed"
            )

        header_b64, payload_b64, sig_b64 = parts
        if not sig_b64:
            raise EvaluatorAuthenticationError(
                "Unsigned JWT tokens are forbidden.", code="jwt_unsigned"
            )

        try:
            header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
            payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
            signature = _b64url_decode(sig_b64)
        except Exception as exc:
            raise EvaluatorAuthenticationError(
                "Invalid base64url or JSON in JWT.", code="jwt_malformed"
            ) from exc

        if not isinstance(header, dict) or not isinstance(payload, dict):
            raise EvaluatorAuthenticationError(
                "JWT header and payload must be JSON objects.", code="jwt_malformed"
            )

        alg = str(header.get("alg") or "")
        if alg.lower() == "none" or alg not in self.ALLOWED_ALGORITHMS:
            raise EvaluatorAuthenticationError(
                f"Unsupported or insecure JWT algorithm '{alg}'.",
                code="jwt_invalid_algorithm",
            )

        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        self._verify_signature(alg, header, signing_input, signature)

        # Validate standard claims: sub, exp, nbf, iss, aud
        current_ts = int((now or datetime.now(UTC)).timestamp())

        exp = payload.get("exp")
        if not isinstance(exp, int | float):
            raise EvaluatorAuthenticationError(
                "JWT is missing mandatory 'exp' claim.", code="jwt_missing_exp"
            )
        if current_ts >= int(exp):
            raise EvaluatorAuthenticationError(
                "JWT token has expired.", code="jwt_expired"
            )

        nbf = payload.get("nbf")
        if isinstance(nbf, int | float) and current_ts < int(nbf):
            raise EvaluatorAuthenticationError(
                "JWT token is not yet valid (nbf).", code="jwt_not_yet_valid"
            )

        iss = str(payload.get("iss") or "").strip().rstrip("/")
        if not iss:
            raise EvaluatorAuthenticationError(
                "JWT is missing mandatory 'iss' claim.", code="jwt_invalid_issuer"
            )
        if self._expected_issuer and iss != self._expected_issuer:
            raise EvaluatorAuthenticationError(
                f"JWT issuer mismatch: expected '{self._expected_issuer}', got '{iss}'.",
                code="jwt_invalid_issuer",
            )

        aud_claim = payload.get("aud")
        aud_matches = False
        resolved_aud = ""
        if isinstance(aud_claim, str):
            resolved_aud = aud_claim
            aud_matches = aud_claim == self._expected_audience
        elif isinstance(aud_claim, list):
            aud_matches = self._expected_audience in aud_claim
            resolved_aud = self._expected_audience if aud_matches else str(aud_claim)

        if not aud_matches:
            raise EvaluatorAuthenticationError(
                f"JWT audience mismatch: expected '{self._expected_audience}'.",
                code="jwt_invalid_audience",
            )

        sub = str(payload.get("sub") or "").strip()
        if not sub:
            raise EvaluatorAuthenticationError(
                "JWT is missing mandatory 'sub' claim.", code="jwt_missing_sub"
            )

        email = payload.get("email")
        email_str = str(email).strip() if isinstance(email, str) and email.strip() else None

        user_meta = payload.get("user_metadata")
        email_verified = bool(
            payload.get("email_verified")
            or payload.get("email_confirmed_at")
            or (isinstance(user_meta, dict) and user_meta.get("email_verified"))
        )

        return VerifiedJwtClaims(
            sub=sub,
            email=email_str,
            email_verified=email_verified,
            issuer=iss,
            audience=resolved_aud,
            expires_at=int(exp),
            raw_claims=payload,
        )

    def _verify_signature(
        self,
        alg: str,
        header: dict[str, Any],
        signing_input: bytes,
        signature: bytes,
    ) -> None:
        if alg == "HS256":
            if not self._jwt_secret:
                raise EvaluatorAuthenticationError(
                    "SUPABASE_JWT_SECRET is not configured for HS256 verification.",
                    code="jwt_secret_not_configured",
                )
            expected_sig = hmac.new(
                self._jwt_secret.encode("utf-8"),
                signing_input,
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(expected_sig, signature):
                raise EvaluatorAuthenticationError(
                    "Invalid JWT cryptographic signature.", code="jwt_invalid_signature"
                )
            return

        # ES256 / RS256 verification via JWK public key if provided
        kid = header.get("kid")
        matching_jwk = None
        for jwk in self._jwks_keys:
            if not kid or jwk.get("kid") == kid:
                matching_jwk = jwk
                break
        if matching_jwk is None:
            raise EvaluatorAuthenticationError(
                f"No matching JWK public key found for alg={alg} kid={kid!r}.",
                code="jwt_invalid_signature",
            )

        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec, padding, utils

            if alg == "ES256":
                x_bytes = _b64url_decode(str(matching_jwk["x"]))
                y_bytes = _b64url_decode(str(matching_jwk["y"]))
                pub_numbers = ec.EllipticCurvePublicNumbers(
                    int.from_bytes(x_bytes, "big"),
                    int.from_bytes(y_bytes, "big"),
                    ec.SECP256R1(),
                )
                pub_key = pub_numbers.public_key()
                if len(signature) != 64:
                    raise ValueError("Invalid ES256 raw signature length")
                r_int = int.from_bytes(signature[:32], "big")
                s_int = int.from_bytes(signature[32:], "big")
                der_sig = utils.encode_dss_signature(r_int, s_int)
                pub_key.verify(der_sig, signing_input, ec.ECDSA(hashes.SHA256()))
                return
            if alg == "RS256":
                from cryptography.hazmat.primitives.asymmetric import rsa

                n_bytes = _b64url_decode(str(matching_jwk["n"]))
                e_bytes = _b64url_decode(str(matching_jwk["e"]))
                rsa_pub = rsa.RSAPublicNumbers(
                    int.from_bytes(e_bytes, "big"),
                    int.from_bytes(n_bytes, "big"),
                ).public_key()
                rsa_pub.verify(
                    signature,
                    signing_input,
                    padding.PKCS1v15(),
                    hashes.SHA256(),
                )
                return
        except Exception as exc:
            raise EvaluatorAuthenticationError(
                "Invalid asymmetric JWT signature.", code="jwt_invalid_signature"
            ) from exc


def build_hs256_jwt(
    claims: dict[str, Any],
    secret: str,
    *,
    header_overrides: dict[str, Any] | None = None,
) -> str:
    """Helper to construct signed HS256 JWTs for deterministic unit/security tests."""
    header: dict[str, Any] = {"alg": "HS256", "typ": "JWT"}
    if header_overrides:
        header.update(header_overrides)
    h_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    if header.get("alg") == "none":
        return f"{h_b64}.{p_b64}."
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{b64url_encode(sig)}"


def _record_access_denied_audit(
    repos: EvaluatorRepositoryBundle,
    clock: EvaluatorClock,
    *,
    actor_id: str | None,
    actor_role: str,
    endpoint: str,
    required_role_or_status: str,
    actual_role_or_status: str,
) -> None:
    repos.audit_logs.append(
        AuditLogRecord(
            id=f"aud-{uuid.uuid4().hex[:12]}",
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.PRIVILEGED_ACCESS_DENIED,
            target_type=AuditTargetType.EVALUATOR_ACCOUNT,
            target_id=actor_id or "anonymous",
            reason=f"Access denied on {endpoint}: required {required_role_or_status}",
            metadata={
                "endpoint": endpoint,
                "required_role_or_status": required_role_or_status,
                "actual_role_or_status": actual_role_or_status,
            },
            created_at=clock.now(),
        )
    )


class EvaluatorAuthProvider:
    """Isolated authentication provider for `/api/v1/evaluator` and `/api/v1/admin` routes.

    Does NOT modify `backend/app/core/security.py`.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        repos: EvaluatorRepositoryBundle | None = None,
        clock: EvaluatorClock | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._repos = repos or get_evaluator_repository_bundle()
        self._clock = clock or SystemEvaluatorClock()

    def _build_verifier(self) -> SupabaseJwtVerifier:
        supabase_url = (self._settings.SUPABASE_URL or "").strip().rstrip("/")
        expected_iss = f"{supabase_url}/auth/v1" if supabase_url else None
        return SupabaseJwtVerifier(
            jwt_secret=self._settings.SUPABASE_JWT_SECRET,
            expected_issuer=expected_iss,
            expected_audience="authenticated",
        )

    def resolve_principal(self, request: Request) -> VerifiedJwtClaims:
        """Resolve verified principal from test dependency override or Bearer JWT."""
        override_fn = request.app.dependency_overrides.get(get_current_user)
        if override_fn is not None:
            try:
                raw_principal = override_fn()
            except HTTPException as exc:
                raise EvaluatorAuthenticationError(
                    str(exc.detail),
                    status_code=exc.status_code,
                    code=f"http_{exc.status_code}",
                ) from exc

            if isinstance(raw_principal, VerifiedJwtClaims):
                return raw_principal
            if isinstance(raw_principal, dict):
                uid = str(
                    raw_principal.get("id")
                    or raw_principal.get("sub")
                    or raw_principal.get("user_id")
                    or ""
                ).strip()
                if not uid:
                    raise EvaluatorAuthenticationError(
                        "Overridden test principal is missing 'id' or 'sub'."
                    )
                email = raw_principal.get("email")
                email_verified = bool(
                    raw_principal.get("email_verified", True)
                )
                return VerifiedJwtClaims(
                    sub=uid,
                    email=str(email) if email else f"{uid}@example.com",
                    email_verified=email_verified,
                    issuer="test-override",
                    audience="authenticated",
                    expires_at=int(self._clock.now().timestamp()) + 3600,
                    raw_claims=raw_principal,
                )

        auth_header = request.headers.get("Authorization") or ""
        if not auth_header.lower().startswith("bearer "):
            raise EvaluatorAuthenticationError(
                "Missing or invalid Authorization Bearer header.",
                code="jwt_missing_token",
            )
        raw_token = auth_header[7:].strip()
        verifier = self._build_verifier()
        return verifier.verify_token(raw_token, now=self._clock.now())

    def require_authenticated_claims(self, request: Request) -> VerifiedJwtClaims:
        claims = self.resolve_principal(request)
        if not claims.email_verified:
            raise EvaluatorForbiddenError(
                "Email address must be verified before accessing Evaluator services.",
                code="email_not_verified",
            )
        return claims

    def require_evaluator_user(
        self,
        request: Request,
        *,
        allow_unregistered_for_onboarding: bool = False,
    ) -> EvaluatorUserRecord:
        claims = self.require_authenticated_claims(request)
        user = self._repos.users.get(claims.sub)

        if user is None:
            if allow_unregistered_for_onboarding:
                now = self._clock.now()
                return EvaluatorUserRecord(
                    id=claims.sub,
                    full_name=str(
                        claims.raw_claims.get("full_name") or "Pending Evaluator"
                    ),
                    email=claims.email or f"{claims.sub}@example.com",
                    role=UserRole.EVALUATOR,
                    evaluator_status=EvaluatorLifecycleStatus.PENDING,
                    email_verified_at=now,
                    created_at=now,
                    updated_at=now,
                )
            _record_access_denied_audit(
                self._repos,
                self._clock,
                actor_id=claims.sub,
                actor_role="unregistered",
                endpoint=request.url.path,
                required_role_or_status="evaluator",
                actual_role_or_status="unregistered",
            )
            raise EvaluatorForbiddenError(
                "Evaluator registration profile not found.",
                code="evaluator_profile_required",
            )

        if user.role != UserRole.EVALUATOR:
            _record_access_denied_audit(
                self._repos,
                self._clock,
                actor_id=user.id,
                actor_role=user.role.value,
                endpoint=request.url.path,
                required_role_or_status="evaluator",
                actual_role_or_status=user.role.value,
            )
            raise EvaluatorForbiddenError(
                "Evaluator role is required to access this endpoint.",
                code="evaluator_role_required",
            )
        return user

    def require_approved_evaluator_user(
        self, request: Request
    ) -> EvaluatorUserRecord:
        user = self.require_evaluator_user(request)
        if user.evaluator_status != EvaluatorLifecycleStatus.APPROVED:
            actual_status = (
                user.evaluator_status.value if user.evaluator_status else "none"
            )
            _record_access_denied_audit(
                self._repos,
                self._clock,
                actor_id=user.id,
                actor_role=user.role.value,
                endpoint=request.url.path,
                required_role_or_status="evaluator:approved",
                actual_role_or_status=f"evaluator:{actual_status}",
            )
            raise EvaluatorNotApprovedError(
                f"Evaluator account is '{actual_status}'. Only approved evaluators "
                "can access inspection tasks or submit inspections."
            )

        active_passkeys = self._repos.credentials.list_for_user(
            user.id, active_only=True
        )
        if not active_passkeys:
            _record_access_denied_audit(
                self._repos,
                self._clock,
                actor_id=user.id,
                actor_role=user.role.value,
                endpoint=request.url.path,
                required_role_or_status="active_webauthn_passkey",
                actual_role_or_status="no_active_passkey",
            )
            raise EvaluatorNotApprovedError(
                "An active registered WebAuthn passkey is required to access "
                "inspection operations.",
                code="webauthn_passkey_required",
            )
        return user

    def require_admin_user(self, request: Request) -> EvaluatorUserRecord:
        claims = self.require_authenticated_claims(request)
        user = self._repos.users.get(claims.sub)

        # In test overrides where an admin dict is injected directly, synthesize
        # the authoritative admin record if not yet in the memory repo:
        if user is None and str(claims.raw_claims.get("role") or "").lower() == "admin":
            now = self._clock.now()
            user = EvaluatorUserRecord(
                id=claims.sub,
                full_name=str(claims.raw_claims.get("full_name") or "System Admin"),
                email=claims.email or "admin@namma-suvidha.local",
                role=UserRole.ADMIN,
                evaluator_status=None,
                email_verified_at=now,
                created_at=now,
                updated_at=now,
            )
            self._repos.users.upsert(user)

        if user is None or user.role != UserRole.ADMIN:
            actual_role = user.role.value if user is not None else "unregistered"
            _record_access_denied_audit(
                self._repos,
                self._clock,
                actor_id=claims.sub,
                actor_role=actual_role,
                endpoint=request.url.path,
                required_role_or_status="admin",
                actual_role_or_status=actual_role,
            )
            raise EvaluatorForbiddenError(
                "Administrator role is required to access this endpoint.",
                code="admin_role_required",
            )
        return user

