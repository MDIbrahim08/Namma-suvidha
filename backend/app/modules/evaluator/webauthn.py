"""Cryptographic WebAuthn / FIDO2 Registration & Assertion Verification Service.

OWNER: Ibrahim (Evaluator & Inspection workflow integration)
COORDINATES WITH: Shabaz (Authentication & Cryptographic Verification Owner)

Enforces Condition 5:
- Never treats a `credential_id` string alone as authentication.
- Generates high-entropy random challenges (`secrets.token_bytes(32)`) bound to
  `user_id`, `purpose`, `rp_id`, `expected_origin`, `operation_context`, and a 5-minute TTL.
- Atomically consumes challenges (`consume_atomically`) to prevent replay attacks.
- Verifies `clientDataJSON.type`, `clientDataJSON.challenge`, `clientDataJSON.origin`,
  `authenticatorData.rpIdHash == SHA256(rp_id)`, `UP=1` (User Present), and `UV=1`
  (User Verified).
- Cryptographically verifies ECDSA P-256 (`ES256`, alg `-7`) and RSA (`RS256`, alg `-257`)
  signatures over `authenticatorData || SHA256(clientDataJSON)`.
- Enforces credential ownership (`user_id`), revocation (`revoked_at IS NULL`),
  monotonic signature counter progression (`assertion.sign_count > stored.sign_count`),
  and first-use counter calibration or `409 webauthn_legacy_re_registration_required`
  for legacy credentials migrated from `public.users`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import struct
import uuid
from datetime import timedelta
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa, utils

from app.modules.evaluator.config import (
    EvaluatorModuleSettings,
    get_evaluator_module_settings,
)
from app.modules.evaluator.domain import (
    AuditLogRecord,
    EvaluatorUserRecord,
    WebAuthnChallengeRecord,
    WebAuthnCredentialRecord,
)
from app.modules.evaluator.enums import (
    AuditAction,
    AuditTargetType,
    WebAuthnChallengePurpose,
    WebAuthnMigrationSource,
)
from app.modules.evaluator.exceptions import (
    EvaluatorForbiddenError,
    EvaluatorNotFoundError,
    WebAuthnLegacyReRegistrationRequiredError,
    WebAuthnVerificationError,
)
from app.modules.evaluator.interfaces import EvaluatorClock, SystemEvaluatorClock
from app.modules.evaluator.repositories import (
    EvaluatorRepositoryBundle,
    get_evaluator_repository_bundle,
)

# AuthenticatorData flags
FLAG_UP = 0x01  # Bit 0: User Present
FLAG_UV = 0x04  # Bit 2: User Verified
FLAG_BE = 0x08  # Bit 3: Backup Eligibility
FLAG_BS = 0x10  # Bit 4: Backup State
FLAG_AT = 0x40  # Bit 6: Attested Credential Data Present


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    if not text or not isinstance(text, str):
        raise WebAuthnVerificationError("Empty or invalid base64url field.")
    cleaned = text.strip()
    padded = cleaned + "=" * (-len(cleaned) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:
        raise WebAuthnVerificationError("Malformed base64url encoding.") from exc


def parse_public_key_envelope(public_key_b64: str) -> dict[str, Any]:
    """Decode and validate a stored COSE/JWK public key envelope (`alg` -7 ES256 or -257 RS256).

    Rejects placeholder or unparseable legacy strings so the caller can prompt
    re-registration (`409 webauthn_legacy_re_registration_required`).
    """
    try:
        raw = b64url_decode(public_key_b64)
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Public key is not a valid encoded key structure.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Public key structure must be a mapping.")

    alg = parsed.get("alg")
    kty = parsed.get("kty")
    if alg == -7 or alg == "ES256" or kty == "EC":
        x_b64 = parsed.get("x")
        y_b64 = parsed.get("y")
        if not isinstance(x_b64, str) or not isinstance(y_b64, str):
            raise ValueError("EC public key is missing 'x' or 'y' coordinates.")
        x_bytes = b64url_decode(x_b64)
        y_bytes = b64url_decode(y_b64)
        if len(x_bytes) != 32 or len(y_bytes) != 32:
            raise ValueError("P-256 coordinates must be 32 bytes each.")
        return {"alg": -7, "kty": "EC", "x": x_bytes, "y": y_bytes}

    if alg == -257 or alg == "RS256" or kty == "RSA":
        n_b64 = parsed.get("n")
        e_b64 = parsed.get("e")
        if not isinstance(n_b64, str) or not isinstance(e_b64, str):
            raise ValueError("RSA public key is missing 'n' or 'e' parameters.")
        n_bytes = b64url_decode(n_b64)
        e_bytes = b64url_decode(e_b64)
        if len(n_bytes) < 256 or len(e_bytes) < 1:
            raise ValueError("RSA modulus must be at least 2048 bits.")
        return {"alg": -257, "kty": "RSA", "n": n_bytes, "e": e_bytes}

    raise ValueError(f"Unsupported COSE key algorithm: {alg!r}")


def encode_es256_public_key(public_key: ec.EllipticCurvePublicKey) -> str:
    nums = public_key.public_numbers()
    x_bytes = nums.x.to_bytes(32, "big")
    y_bytes = nums.y.to_bytes(32, "big")
    envelope = {
        "kty": "EC",
        "alg": -7,
        "crv": "P-256",
        "x": b64url_encode(x_bytes),
        "y": b64url_encode(y_bytes),
    }
    return b64url_encode(json.dumps(envelope, separators=(",", ":")).encode("utf-8"))


def verify_cose_signature(
    public_key_b64: str,
    signed_data: bytes,
    signature_bytes: bytes,
) -> None:
    """Verify ECDSA P-256 (DER or raw R||S) or RSA PKCS1v15 SHA-256 signature."""
    key_info = parse_public_key_envelope(public_key_b64)
    if key_info["alg"] == -7:
        pub_numbers = ec.EllipticCurvePublicNumbers(
            int.from_bytes(key_info["x"], "big"),
            int.from_bytes(key_info["y"], "big"),
            ec.SECP256R1(),
        )
        pub_key = pub_numbers.public_key()
        der_sig = signature_bytes
        if len(signature_bytes) == 64 and signature_bytes[0] != 0x30:
            r_int = int.from_bytes(signature_bytes[:32], "big")
            s_int = int.from_bytes(signature_bytes[32:], "big")
            der_sig = utils.encode_dss_signature(r_int, s_int)
        try:
            pub_key.verify(der_sig, signed_data, ec.ECDSA(hashes.SHA256()))
        except InvalidSignature as exc:
            raise WebAuthnVerificationError(
                "Cryptographic WebAuthn ECDSA signature verification failed.",
                code="webauthn_invalid_signature",
            ) from exc
        return

    if key_info["alg"] == -257:
        rsa_pub = rsa.RSAPublicNumbers(
            int.from_bytes(key_info["e"], "big"),
            int.from_bytes(key_info["n"], "big"),
        ).public_key()
        try:
            rsa_pub.verify(
                signature_bytes,
                signed_data,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except InvalidSignature as exc:
            raise WebAuthnVerificationError(
                "Cryptographic WebAuthn RSA signature verification failed.",
                code="webauthn_invalid_signature",
            ) from exc


def parse_authenticator_data(auth_data: bytes) -> dict[str, Any]:
    """Parse binary WebAuthn `authenticatorData` (min 37 bytes)."""
    if len(auth_data) < 37:
        raise WebAuthnVerificationError(
            "authenticatorData is shorter than the mandatory 37-byte header.",
            code="webauthn_malformed_auth_data",
        )
    rp_id_hash = auth_data[:32]
    flags = auth_data[32]
    sign_count = struct.unpack(">I", auth_data[33:37])[0]

    result: dict[str, Any] = {
        "rp_id_hash": rp_id_hash,
        "flags": flags,
        "up": bool(flags & FLAG_UP),
        "uv": bool(flags & FLAG_UV),
        "be": bool(flags & FLAG_BE),
        "bs": bool(flags & FLAG_BS),
        "at": bool(flags & FLAG_AT),
        "sign_count": sign_count,
        "aaguid": None,
        "credential_id": None,
        "credential_public_key_b64": None,
    }

    if result["at"]:
        if len(auth_data) < 55:
            raise WebAuthnVerificationError(
                "Attested credential data flag set, but authenticatorData is truncated.",
                code="webauthn_malformed_auth_data",
            )
        aaguid_bytes = auth_data[37:53]
        cred_id_len = struct.unpack(">H", auth_data[53:55])[0]
        end_cred_id = 55 + cred_id_len
        if len(auth_data) < end_cred_id:
            raise WebAuthnVerificationError(
                "authenticatorData truncated inside credential_id.",
                code="webauthn_malformed_auth_data",
            )
        cred_id_bytes = auth_data[55:end_cred_id]
        pub_key_bytes = auth_data[end_cred_id:]
        result["aaguid"] = str(uuid.UUID(bytes=aaguid_bytes))
        result["credential_id"] = b64url_encode(cred_id_bytes)
        if pub_key_bytes:
            result["credential_public_key_b64"] = b64url_encode(pub_key_bytes)

    return result


class WebAuthnService:
    """Service managing WebAuthn registration options/verification, authentication
    options/assertion verification, legacy credential counter calibration, and
    credential revocation.
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

    def generate_registration_options(
        self,
        user: EvaluatorUserRecord,
        *,
        origin: str | None = None,
    ) -> dict[str, Any]:
        now = self._clock.now()
        expected_origin = (
            origin
            if origin and origin in self._settings.WEBAUTHN_EXPECTED_ORIGINS
            else self._settings.WEBAUTHN_EXPECTED_ORIGINS[0]
        )
        challenge_str = b64url_encode(secrets.token_bytes(32))
        challenge_rec = WebAuthnChallengeRecord(
            id=f"chal-{uuid.uuid4().hex[:12]}",
            user_id=user.id,
            challenge=challenge_str,
            purpose=WebAuthnChallengePurpose.REGISTRATION,
            operation_context={},
            rp_id=self._settings.WEBAUTHN_RP_ID,
            expected_origin=expected_origin,
            user_verification="required",
            expires_at=now
            + timedelta(seconds=self._settings.WEBAUTHN_CHALLENGE_TTL_SECONDS),
            created_at=now,
        )
        self._repos.challenges.create(challenge_rec)

        existing_creds = self._repos.credentials.list_for_user(
            user.id, active_only=True
        )
        exclude_credentials = [
            {
                "type": "public-key",
                "id": c.credential_id,
                "transports": c.transports,
            }
            for c in existing_creds
        ]

        return {
            "rp": {
                "id": self._settings.WEBAUTHN_RP_ID,
                "name": self._settings.WEBAUTHN_RP_NAME,
            },
            "user": {
                "id": b64url_encode(user.id.encode("utf-8")),
                "name": user.email,
                "displayName": user.full_name,
            },
            "challenge": challenge_str,
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},
                {"type": "public-key", "alg": -257},
            ],
            "timeout": 60000,
            "excludeCredentials": exclude_credentials,
            "authenticatorSelection": {
                "userVerification": "required",
                "residentKey": "preferred",
            },
            "attestation": "none",
        }

    def verify_registration(
        self,
        user: EvaluatorUserRecord,
        *,
        credential_id: str,
        client_data_json_b64: str,
        authenticator_data_b64: str,
        public_key_b64: str | None = None,
        transports: list[str] | None = None,
        device_name: str = "Registered Passkey",
    ) -> WebAuthnCredentialRecord:
        now = self._clock.now()
        client_data_bytes = b64url_decode(client_data_json_b64)
        try:
            client_data = json.loads(client_data_bytes.decode("utf-8"))
        except Exception as exc:
            raise WebAuthnVerificationError(
                "clientDataJSON is not valid JSON.",
                code="webauthn_malformed_client_data",
            ) from exc

        if client_data.get("type") != "webauthn.create":
            raise WebAuthnVerificationError(
                "clientDataJSON.type must be 'webauthn.create'.",
                code="webauthn_invalid_type",
            )

        challenge_str = str(client_data.get("challenge") or "")
        consumed = self._repos.challenges.consume_atomically(
            challenge=challenge_str,
            user_id=user.id,
            purpose=WebAuthnChallengePurpose.REGISTRATION,
            now=now,
        )
        if consumed is None:
            raise WebAuthnVerificationError(
                "WebAuthn registration challenge is invalid, expired, or already used.",
                code="webauthn_invalid_or_expired_challenge",
            )

        origin = str(client_data.get("origin") or "")
        if origin not in self._settings.WEBAUTHN_EXPECTED_ORIGINS:
            raise WebAuthnVerificationError(
                f"Untrusted WebAuthn origin '{origin}'.",
                code="webauthn_invalid_origin",
            )

        auth_data_bytes = b64url_decode(authenticator_data_b64)
        parsed_auth = parse_authenticator_data(auth_data_bytes)

        expected_rp_hash = hashlib.sha256(
            consumed.rp_id.encode("utf-8")
        ).digest()
        if parsed_auth["rp_id_hash"] != expected_rp_hash:
            raise WebAuthnVerificationError(
                "Authenticator rpIdHash does not match configured WEBAUTHN_RP_ID.",
                code="webauthn_rp_id_mismatch",
            )

        if not parsed_auth["up"]:
            raise WebAuthnVerificationError(
                "Authenticator User Present (UP) flag is not set.",
                code="webauthn_user_presence_required",
            )
        if not parsed_auth["uv"]:
            raise WebAuthnVerificationError(
                "Authenticator User Verification (UV) flag is not set.",
                code="webauthn_user_verification_required",
            )
        if not parsed_auth["at"]:
            raise WebAuthnVerificationError(
                "Attested credential data flag (AT) is required during registration.",
                code="webauthn_missing_attested_credential",
            )

        attested_cred_id = parsed_auth["credential_id"]
        if attested_cred_id and attested_cred_id != credential_id:
            raise WebAuthnVerificationError(
                "Credential ID mismatch between envelope and authenticatorData.",
                code="webauthn_credential_id_mismatch",
            )

        resolved_pub_key = (
            public_key_b64 or parsed_auth["credential_public_key_b64"]
        )
        if not resolved_pub_key:
            raise WebAuthnVerificationError(
                "Missing COSE public key in registration payload.",
                code="webauthn_invalid_public_key",
            )

        try:
            parse_public_key_envelope(resolved_pub_key)
        except ValueError as exc:
            raise WebAuthnVerificationError(
                f"Invalid COSE public key: {exc}",
                code="webauthn_invalid_public_key",
            ) from exc

        record = WebAuthnCredentialRecord(
            id=f"pk-{uuid.uuid4().hex[:12]}",
            user_id=user.id,
            credential_id=credential_id,
            public_key=resolved_pub_key,
            sign_count=int(parsed_auth["sign_count"]),
            sign_count_initialized=True,
            migration_source=WebAuthnMigrationSource.NATIVE,
            aaguid=parsed_auth["aaguid"],
            transports=transports or ["internal"],
            device_name=device_name.strip() or "Registered Passkey",
            backed_up=bool(parsed_auth["bs"]),
            user_verified_on_register=True,
            created_at=now,
        )
        saved = self._repos.credentials.upsert(record)

        # Preserve backward compatibility on `public.users` if legacy fields are empty
        if not user.webauthn_credential_id:
            self._repos.users.upsert(
                user.model_copy(
                    update={
                        "webauthn_credential_id": saved.credential_id,
                        "webauthn_public_key": saved.public_key,
                        "updated_at": now,
                    }
                )
            )

        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=user.id,
                actor_role=user.role.value,
                action=AuditAction.PASSKEY_REGISTERED,
                target_type=AuditTargetType.WEBAUTHN_PASSKEY,
                target_id=saved.id,
                metadata={
                    "credential_row_id": saved.id,
                    "device_name": saved.device_name,
                    "transports": saved.transports,
                },
                created_at=now,
            )
        )
        return saved

    def generate_authentication_options(
        self,
        user: EvaluatorUserRecord,
        *,
        purpose: WebAuthnChallengePurpose = WebAuthnChallengePurpose.AUTHENTICATION,
        operation_context: dict[str, Any] | None = None,
        origin: str | None = None,
    ) -> dict[str, Any]:
        now = self._clock.now()
        active_creds = self._repos.credentials.list_for_user(
            user.id, active_only=True
        )
        if not active_creds:
            raise WebAuthnVerificationError(
                "No active WebAuthn passkeys registered for this account.",
                code="webauthn_no_active_credentials",
            )

        expected_origin = (
            origin
            if origin and origin in self._settings.WEBAUTHN_EXPECTED_ORIGINS
            else self._settings.WEBAUTHN_EXPECTED_ORIGINS[0]
        )
        challenge_str = b64url_encode(secrets.token_bytes(32))
        challenge_rec = WebAuthnChallengeRecord(
            id=f"chal-{uuid.uuid4().hex[:12]}",
            user_id=user.id,
            challenge=challenge_str,
            purpose=purpose,
            operation_context=operation_context or {},
            rp_id=self._settings.WEBAUTHN_RP_ID,
            expected_origin=expected_origin,
            user_verification="required",
            expires_at=now
            + timedelta(seconds=self._settings.WEBAUTHN_CHALLENGE_TTL_SECONDS),
            created_at=now,
        )
        self._repos.challenges.create(challenge_rec)

        return {
            "challenge": challenge_str,
            "timeout": 60000,
            "rpId": self._settings.WEBAUTHN_RP_ID,
            "userVerification": "required",
            "allowCredentials": [
                {
                    "type": "public-key",
                    "id": c.credential_id,
                    "transports": c.transports,
                }
                for c in active_creds
            ],
        }

    def verify_assertion(
        self,
        user: EvaluatorUserRecord,
        *,
        credential_id: str | None,
        client_data_json_b64: str | None,
        authenticator_data_b64: str | None,
        signature_b64: str | None,
        purpose: WebAuthnChallengePurpose = WebAuthnChallengePurpose.AUTHENTICATION,
        expected_operation_context: dict[str, Any] | None = None,
    ) -> tuple[WebAuthnCredentialRecord, WebAuthnChallengeRecord]:
        """Cryptographically verify a WebAuthn assertion.

        Explicitly rejects credential-ID-only submissions where `clientDataJSON`,
        `authenticatorData`, or `signature` are missing.
        """
        now = self._clock.now()
        if (
            not credential_id
            or not client_data_json_b64
            or not authenticator_data_b64
            or not signature_b64
        ):
            raise WebAuthnVerificationError(
                "A credential_id alone is never accepted as authentication. "
                "Full cryptographic WebAuthn assertion (clientDataJSON, "
                "authenticatorData, and signature) is required.",
                code="webauthn_assertion_incomplete",
            )

        cred = self._repos.credentials.get_by_credential_id(credential_id)
        if cred is None or cred.user_id != user.id:
            raise WebAuthnVerificationError(
                "WebAuthn credential does not exist or does not belong to the "
                "authenticated evaluator.",
                code="webauthn_credential_not_owned",
            )
        if cred.revoked_at is not None:
            raise WebAuthnVerificationError(
                "WebAuthn credential has been revoked.",
                code="webauthn_credential_revoked",
            )

        # If this is a legacy credential migrated from `public.users`, validate
        # that its stored public_key is a parseable COSE key before proceeding:
        try:
            parse_public_key_envelope(cred.public_key)
        except ValueError as exc:
            if cred.migration_source == WebAuthnMigrationSource.LEGACY_USERS_TABLE:
                raise WebAuthnLegacyReRegistrationRequiredError(
                    "Legacy authenticator key from public.users is not a valid COSE "
                    "public key. Please register a new passkey to continue."
                ) from exc
            raise WebAuthnVerificationError(
                "Stored public key is corrupted.",
                code="webauthn_invalid_public_key",
            ) from exc

        client_data_bytes = b64url_decode(client_data_json_b64)
        try:
            client_data = json.loads(client_data_bytes.decode("utf-8"))
        except Exception as exc:
            raise WebAuthnVerificationError(
                "clientDataJSON is not valid JSON.",
                code="webauthn_malformed_client_data",
            ) from exc

        if client_data.get("type") != "webauthn.get":
            raise WebAuthnVerificationError(
                "clientDataJSON.type must be 'webauthn.get'.",
                code="webauthn_invalid_type",
            )

        challenge_str = str(client_data.get("challenge") or "")
        consumed = self._repos.challenges.consume_atomically(
            challenge=challenge_str,
            user_id=user.id,
            purpose=purpose,
            now=now,
        )
        if consumed is None:
            raise WebAuthnVerificationError(
                "WebAuthn challenge is invalid, expired, or has already been replayed.",
                code="webauthn_challenge_replayed_or_expired",
            )

        if expected_operation_context:
            for k, v in expected_operation_context.items():
                if consumed.operation_context.get(k) != v:
                    raise WebAuthnVerificationError(
                        f"WebAuthn challenge context mismatch on '{k}'.",
                        code="webauthn_context_mismatch",
                    )

        origin = str(client_data.get("origin") or "")
        if origin not in self._settings.WEBAUTHN_EXPECTED_ORIGINS:
            raise WebAuthnVerificationError(
                f"Untrusted WebAuthn origin '{origin}'.",
                code="webauthn_invalid_origin",
            )

        auth_data_bytes = b64url_decode(authenticator_data_b64)
        parsed_auth = parse_authenticator_data(auth_data_bytes)

        expected_rp_hash = hashlib.sha256(
            consumed.rp_id.encode("utf-8")
        ).digest()
        if parsed_auth["rp_id_hash"] != expected_rp_hash:
            raise WebAuthnVerificationError(
                "Authenticator rpIdHash mismatch.",
                code="webauthn_rp_id_mismatch",
            )

        if not parsed_auth["up"]:
            raise WebAuthnVerificationError(
                "User Present (UP) flag is required.",
                code="webauthn_user_presence_required",
            )
        if not parsed_auth["uv"]:
            raise WebAuthnVerificationError(
                "User Verification (UV) flag is required.",
                code="webauthn_user_verification_required",
            )

        # Verify cryptographic signature over authenticatorData || SHA256(clientDataJSON)
        client_data_hash = hashlib.sha256(client_data_bytes).digest()
        signed_bytes = auth_data_bytes + client_data_hash
        sig_bytes = b64url_decode(signature_b64)
        verify_cose_signature(cred.public_key, signed_bytes, sig_bytes)

        reported_count = int(parsed_auth["sign_count"])
        if not cred.sign_count_initialized:
            # First-use counter calibration for legacy migrated credentials
            updated_cred = cred.model_copy(
                update={
                    "sign_count": reported_count,
                    "sign_count_initialized": True,
                    "last_used_at": now,
                }
            )
            self._repos.credentials.upsert(updated_cred)
            self._repos.audit_logs.append(
                AuditLogRecord(
                    id=f"aud-{uuid.uuid4().hex[:12]}",
                    actor_id=user.id,
                    actor_role=user.role.value,
                    action=AuditAction.LEGACY_PASSKEY_CALIBRATED,
                    target_type=AuditTargetType.WEBAUTHN_PASSKEY,
                    target_id=cred.id,
                    metadata={
                        "credential_row_id": cred.id,
                        "calibrated_sign_count": reported_count,
                    },
                    created_at=now,
                )
            )
            return updated_cred, consumed

        # Monotonic signature counter enforcement for initialized credentials
        if (cred.sign_count > 0 or reported_count > 0) and (
            reported_count <= cred.sign_count
        ):
            self._repos.audit_logs.append(
                AuditLogRecord(
                    id=f"aud-{uuid.uuid4().hex[:12]}",
                    actor_id=user.id,
                    actor_role=user.role.value,
                    action=AuditAction.PASSKEY_SIGN_COUNT_ANOMALY,
                    target_type=AuditTargetType.WEBAUTHN_PASSKEY,
                    target_id=cred.id,
                    reason="Authenticator signature counter did not increment (possible cloned key).",
                    metadata={
                        "stored_sign_count": cred.sign_count,
                        "reported_sign_count": reported_count,
                    },
                    created_at=now,
                )
            )
            raise WebAuthnVerificationError(
                "WebAuthn signature counter anomaly detected (possible cloned authenticator).",
                code="webauthn_sign_count_anomaly",
            )

        updated_cred = cred.model_copy(
            update={
                "sign_count": reported_count,
                "last_used_at": now,
            }
        )
        self._repos.credentials.upsert(updated_cred)
        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=user.id,
                actor_role=user.role.value,
                action=AuditAction.PASSKEY_AUTHENTICATED,
                target_type=AuditTargetType.WEBAUTHN_PASSKEY,
                target_id=cred.id,
                metadata={
                    "purpose": purpose.value,
                    "sign_count": reported_count,
                },
                created_at=now,
            )
        )
        return updated_cred, consumed

    def revoke_credential(
        self,
        *,
        actor: EvaluatorUserRecord,
        credential_id_or_row_id: str,
        reason: str = "User or admin requested revocation",
    ) -> WebAuthnCredentialRecord:
        now = self._clock.now()
        cred = self._repos.credentials.get_by_id(
            credential_id_or_row_id
        ) or self._repos.credentials.get_by_credential_id(credential_id_or_row_id)
        if cred is None:
            raise EvaluatorNotFoundError("WebAuthn passkey not found.")

        if actor.role.value != "admin" and cred.user_id != actor.id:
            raise EvaluatorForbiddenError(
                "Cannot revoke a passkey belonging to another user."
            )

        revoked = cred.model_copy(
            update={
                "revoked_at": now,
                "revoked_by": actor.id,
                "revoke_reason": reason,
            }
        )
        self._repos.credentials.upsert(revoked)
        self._repos.audit_logs.append(
            AuditLogRecord(
                id=f"aud-{uuid.uuid4().hex[:12]}",
                actor_id=actor.id,
                actor_role=actor.role.value,
                action=AuditAction.PASSKEY_REVOKED,
                target_type=AuditTargetType.WEBAUTHN_PASSKEY,
                target_id=cred.id,
                reason=reason,
                metadata={
                    "credential_row_id": cred.id,
                    "device_name": cred.device_name,
                    "revoke_reason": reason,
                },
                created_at=now,
            )
        )
        return revoked

