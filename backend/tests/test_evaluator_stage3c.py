"""Stage 3C tests: Cryptographic WebAuthn registration, assertion verification,
replay protection, ownership checks, signature counter anomaly detection,
legacy credential calibration / re-registration, and revocation.
"""

from __future__ import annotations

import hashlib
import json
import struct
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from app.modules.evaluator.domain import EvaluatorUserRecord, WebAuthnCredentialRecord
from app.modules.evaluator.enums import (
    AuditAction,
    EvaluatorLifecycleStatus,
    UserRole,
    WebAuthnChallengePurpose,
    WebAuthnMigrationSource,
)
from app.modules.evaluator.exceptions import (
    EvaluatorForbiddenError,
    WebAuthnLegacyReRegistrationRequiredError,
    WebAuthnVerificationError,
)
from app.modules.evaluator.repositories import get_evaluator_memory_bundle
from app.modules.evaluator.webauthn import (
    FLAG_AT,
    FLAG_UP,
    FLAG_UV,
    WebAuthnService,
    b64url_decode,
    b64url_encode,
    encode_es256_public_key,
)


class FixedClock:
    def __init__(self, dt: datetime) -> None:
        self._dt = dt

    def now(self) -> datetime:
        return self._dt


def build_attestation_auth_data(
    *,
    rp_id: str,
    flags: int,
    sign_count: int,
    credential_id: str,
    public_key_b64: str,
) -> str:
    rp_hash = hashlib.sha256(rp_id.encode("utf-8")).digest()
    header = rp_hash + bytes([flags]) + struct.pack(">I", sign_count)
    aaguid = uuid.UUID("00000000-0000-0000-0000-000000000000").bytes
    cred_id_bytes = b64url_decode(credential_id)
    pub_key_bytes = b64url_decode(public_key_b64)
    attested = (
        aaguid
        + struct.pack(">H", len(cred_id_bytes))
        + cred_id_bytes
        + pub_key_bytes
    )
    return b64url_encode(header + attested)


def build_assertion_payload(
    *,
    private_key: ec.EllipticCurvePrivateKey,
    rp_id: str,
    challenge: str,
    origin: str = "http://localhost:5173",
    flags: int = FLAG_UP | FLAG_UV,
    sign_count: int = 1,
) -> tuple[str, str, str]:
    client_data_bytes = json.dumps(
        {
            "type": "webauthn.get",
            "challenge": challenge,
            "origin": origin,
            "crossOrigin": False,
        }
    ).encode("utf-8")
    rp_hash = hashlib.sha256(rp_id.encode("utf-8")).digest()
    auth_data_bytes = rp_hash + bytes([flags]) + struct.pack(">I", sign_count)
    signed_input = auth_data_bytes + hashlib.sha256(client_data_bytes).digest()
    der_sig = private_key.sign(signed_input, ec.ECDSA(hashes.SHA256()))
    return (
        b64url_encode(client_data_bytes),
        b64url_encode(auth_data_bytes),
        b64url_encode(der_sig),
    )


def test_stage3c_webauthn_registration_and_cryptographic_assertion_lifecycle() -> None:
    now = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)
    bundle = get_evaluator_memory_bundle()
    bundle.clear_all()
    svc = WebAuthnService(repos=bundle, clock=FixedClock(now))

    user = EvaluatorUserRecord(
        id="eval-201",
        full_name="Karthik S",
        email="karthik@example.com",
        role=UserRole.EVALUATOR,
        evaluator_status=EvaluatorLifecycleStatus.APPROVED,
        created_at=now,
        updated_at=now,
    )
    bundle.users.upsert(user)

    # 1. Generate registration options
    reg_opts = svc.generate_registration_options(user)
    challenge = reg_opts["challenge"]
    assert reg_opts["rp"]["id"] == "localhost"

    # 2. Generate real P-256 keypair and register passkey
    priv_key = ec.generate_private_key(ec.SECP256R1())
    pub_key_b64 = encode_es256_public_key(priv_key.public_key())
    cred_id = b64url_encode(b"hardware-passkey-001")

    reg_client_data = b64url_encode(
        json.dumps(
            {
                "type": "webauthn.create",
                "challenge": challenge,
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

    saved_cred = svc.verify_registration(
        user,
        credential_id=cred_id,
        client_data_json_b64=reg_client_data,
        authenticator_data_b64=reg_auth_data,
        device_name="Karthik Pixel Passkey",
    )
    assert saved_cred.credential_id == cred_id
    assert saved_cred.sign_count == 1
    assert saved_cred.sign_count_initialized is True

    # 3. Never accept a credential_id alone without signature/challenge
    with pytest.raises(WebAuthnVerificationError) as inc_exc:
        svc.verify_assertion(
            user,
            credential_id=cred_id,
            client_data_json_b64=None,
            authenticator_data_b64=None,
            signature_b64=None,
        )
    assert inc_exc.value.code == "webauthn_assertion_incomplete"

    # 4. Generate authentication challenge & verify valid ECDSA P-256 assertion
    auth_opts = svc.generate_authentication_options(
        user,
        purpose=WebAuthnChallengePurpose.INSPECTION_SUBMIT,
        operation_context={"task_id": "tsk-777"},
    )
    auth_challenge = auth_opts["challenge"]
    c_b64, a_b64, s_b64 = build_assertion_payload(
        private_key=priv_key,
        rp_id="localhost",
        challenge=auth_challenge,
        sign_count=2,
    )
    verified_cred, consumed_chal = svc.verify_assertion(
        user,
        credential_id=cred_id,
        client_data_json_b64=c_b64,
        authenticator_data_b64=a_b64,
        signature_b64=s_b64,
        purpose=WebAuthnChallengePurpose.INSPECTION_SUBMIT,
        expected_operation_context={"task_id": "tsk-777"},
    )
    assert verified_cred.sign_count == 2
    assert consumed_chal.consumed_at == now

    # 5. Replay protection: submitting the exact same assertion again MUST fail
    with pytest.raises(WebAuthnVerificationError) as replay_exc:
        svc.verify_assertion(
            user,
            credential_id=cred_id,
            client_data_json_b64=c_b64,
            authenticator_data_b64=a_b64,
            signature_b64=s_b64,
            purpose=WebAuthnChallengePurpose.INSPECTION_SUBMIT,
            expected_operation_context={"task_id": "tsk-777"},
        )
    assert replay_exc.value.code == "webauthn_challenge_replayed_or_expired"

    # 6. Signature counter regression / clone detection (`reported <= stored`)
    auth_opts_2 = svc.generate_authentication_options(user)
    c2, a2, s2 = build_assertion_payload(
        private_key=priv_key,
        rp_id="localhost",
        challenge=auth_opts_2["challenge"],
        sign_count=2,  # Did not increment above stored sign_count=2!
    )
    with pytest.raises(WebAuthnVerificationError) as clone_exc:
        svc.verify_assertion(
            user,
            credential_id=cred_id,
            client_data_json_b64=c2,
            authenticator_data_b64=a2,
            signature_b64=s2,
        )
    assert clone_exc.value.code == "webauthn_sign_count_anomaly"

    # 7. Cross-account ownership check: another user cannot use Karthik's credential_id
    other_user = user.model_copy(
        update={"id": "eval-999", "email": "other@example.com"}
    )
    bundle.users.upsert(other_user)
    with pytest.raises(WebAuthnVerificationError) as own_exc:
        svc.verify_assertion(
            other_user,
            credential_id=cred_id,
            client_data_json_b64=c2,
            authenticator_data_b64=a2,
            signature_b64=s2,
        )
    assert own_exc.value.code == "webauthn_credential_not_owned"

    # 8. Credential revocation blocks future authentication
    with pytest.raises(EvaluatorForbiddenError):
        svc.revoke_credential(
            actor=other_user, credential_id_or_row_id=cred_id
        )

    svc.revoke_credential(
        actor=user, credential_id_or_row_id=cred_id, reason="Lost device"
    )
    with pytest.raises(WebAuthnVerificationError) as rev_exc:
        svc.verify_assertion(
            user,
            credential_id=cred_id,
            client_data_json_b64=c2,
            authenticator_data_b64=a2,
            signature_b64=s2,
        )
    assert rev_exc.value.code == "webauthn_credential_revoked"


def test_stage3c_legacy_migrated_credential_calibration_and_invalid_key_re_registration() -> None:
    now = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)
    bundle = get_evaluator_memory_bundle()
    bundle.clear_all()
    svc = WebAuthnService(repos=bundle, clock=FixedClock(now))

    user = EvaluatorUserRecord(
        id="eval-legacy-1",
        full_name="Legacy Evaluator",
        email="legacy@example.com",
        role=UserRole.EVALUATOR,
        evaluator_status=EvaluatorLifecycleStatus.APPROVED,
        created_at=now - timedelta(days=30),
        updated_at=now,
    )
    bundle.users.upsert(user)

    # Case A: Invalid / placeholder legacy public key -> raises 409 re-registration required
    bad_legacy_cred = WebAuthnCredentialRecord(
        id="cred-bad-legacy",
        user_id=user.id,
        credential_id=b64url_encode(b"legacy-bad-cred"),
        public_key="not-a-valid-cose-key",
        sign_count=0,
        sign_count_initialized=False,
        migration_source=WebAuthnMigrationSource.LEGACY_USERS_TABLE,
        created_at=now - timedelta(days=30),
    )
    bundle.credentials.upsert(bad_legacy_cred)

    opts_a = svc.generate_authentication_options(user)
    with pytest.raises(WebAuthnLegacyReRegistrationRequiredError) as leg_exc:
        svc.verify_assertion(
            user,
            credential_id=bad_legacy_cred.credential_id,
            client_data_json_b64="e30",
            authenticator_data_b64="e30",
            signature_b64="e30",
        )
    assert leg_exc.value.code == "webauthn_legacy_re_registration_required"
    assert leg_exc.value.status_code == 409
    _ = opts_a

    # Case B: Valid legacy COSE key with sign_count_initialized=False -> first use calibrates counter!
    priv_key = ec.generate_private_key(ec.SECP256R1())
    valid_legacy_cred = WebAuthnCredentialRecord(
        id="cred-good-legacy",
        user_id=user.id,
        credential_id=b64url_encode(b"legacy-good-cred"),
        public_key=encode_es256_public_key(priv_key.public_key()),
        sign_count=0,
        sign_count_initialized=False,
        migration_source=WebAuthnMigrationSource.LEGACY_USERS_TABLE,
        created_at=now - timedelta(days=30),
    )
    bundle.credentials.upsert(valid_legacy_cred)

    opts_b = svc.generate_authentication_options(user)
    # Authenticator reports internal hardware counter = 42 on first post-migration use
    c_b, a_b, s_b = build_assertion_payload(
        private_key=priv_key,
        rp_id="localhost",
        challenge=opts_b["challenge"],
        sign_count=42,
    )
    calibrated_cred, _ = svc.verify_assertion(
        user,
        credential_id=valid_legacy_cred.credential_id,
        client_data_json_b64=c_b,
        authenticator_data_b64=a_b,
        signature_b64=s_b,
    )
    assert calibrated_cred.sign_count == 42
    assert calibrated_cred.sign_count_initialized is True

    cal_logs = bundle.audit_logs.list_logs(
        action=AuditAction.LEGACY_PASSKEY_CALIBRATED
    )
    assert len(cal_logs) == 1
    assert cal_logs[0].metadata["calibrated_sign_count"] == 42

