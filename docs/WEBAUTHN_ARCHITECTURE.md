# PROPOSED — AWAITING SHABAZ & SHUBHAM'S APPROVAL —WEBAUTHN / FIDO2 PASSKEY ARCHITECTURE

**Document:** `docs/WEBAUTHN_ARCHITECTURE.md`  
**Stage:** Stage 2 — WebAuthn / FIDO2 Passkey Registration, Authentication & Inspection Submission Verification Architecture  
**Owners:** **Shabaz** (Authentication & Cryptographic Verification Owner) / **Ibrahim** (Evaluator & Inspection Workflow Integration) / **Shubham** (Database Schema Owner)

---

## 1. Fundamental Security Rule: A Credential ID Is Not Authentication

In WebAuthn (W3C Web Authentication API / FIDO2 CTAP2):
- A `credential_id` is a **public identifier** (analogous to a username or public key handle).
- Accepting `{ "credential_id": "..." }` from the browser as proof of biometric verification is completely insecure because any attacker who knows or intercepts the string can replay it.
- **Genuine WebAuthn security requires cryptographic challenge-response verification:**
  1. The server generates a fresh, high-entropy random `challenge` (at least 32 bytes from `secrets.token_bytes(32)`), stores it with a short expiry (`5 minutes`), and binds it to the authenticated `user_id` and `purpose` (`registration`, `authentication`, or `inspection_submit`).
  2. The browser passes the challenge to `navigator.credentials.create()` or `navigator.credentials.get()`.
  3. The device authenticator (Android Biometric/Keystore, iOS Secure Enclave / Face ID / Touch ID, Windows Hello TPM, or hardware security key) verifies the user locally (`UV = 1`) and signs `authenticatorData || SHA256(clientDataJSON)` using the hardware-bound private key.
  4. The FastAPI backend cryptographically verifies the signature using the user's stored COSE `public_key`, validates the challenge, origin, Relying Party ID (`rpIdHash`), `UP` (User Present) and `UV` (User Verified) flags, and monotonic `sign_count`, and atomically marks the challenge as consumed (`consumed_at = now()`).

> **Zero Biometric Data Collection:** The Namma Suvidha frontend and backend **never** access, transmit, or store fingerprint images, facial images, voiceprints, or biometric templates. Biometric unlocking happens strictly inside the user's device OS/TEE, and only standard FIDO2 public keys and cryptographic signatures cross the network.

---

## 2. Relying Party (RP) Configuration

Configured via environment variables in `backend/app/core/config.py`:

| Setting | Development Default | Production Requirement | Purpose |
| :--- | :--- | :--- | :--- |
| `WEBAUTHN_RP_ID` | `localhost` | Exact effective domain (e.g. `nammasuvidha.in`) | Validated against `SHA-256(rp_id) == authData.rpIdHash` |
| `WEBAUTHN_RP_NAME` | `Namma Suvidha Evaluator` | `Namma Suvidha Evaluator` | Displayed in browser/OS passkey prompt |
| `WEBAUTHN_EXPECTED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | `https://nammasuvidha.in` (HTTPS mandatory) | Validated against `clientDataJSON.origin` |
| `WEBAUTHN_CHALLENGE_TTL_SECONDS` | `300` (5 minutes) | `300` (5 minutes) | Maximum lifetime of an unconsumed challenge |

---

## 3. Passkey Registration Flow (`navigator.credentials.create()`)

### 3.1 Step A — Request Registration Options (`POST /api/v1/evaluators/passkeys/register/options`)
1. **Preconditions:** Caller must pass `require_evaluator` (valid Supabase JWT, verified email).
2. **Challenge Generation:**
   - Generate 32 random bytes via `secrets.token_urlsafe(32)`.
   - Insert row into `public.webauthn_challenges`:
     - `user_id = current_user.id`
     - `challenge = <base64url>`
     - `purpose = 'registration'`
     - `rp_id = settings.WEBAUTHN_RP_ID`
     - `expected_origin = <matched origin>`
     - `user_verification = 'required'`
     - `expires_at = now() + 300s`
3. **Exclude Existing Credentials:**
   - Query active (non-revoked) `credential_id` values for `user_id` from `public.webauthn_credentials` and populate `excludeCredentials` so the same authenticator does not register duplicate credentials.
4. **Response (`PublicKeyCredentialCreationOptionsJSON`):**
   - `rp`: `{ "id": rp_id, "name": rp_name }`
   - `user`: `{ "id": base64url(user_id.bytes), "name": user.email, "displayName": user.full_name }`
   - `challenge`: `<base64url>`
   - `pubKeyCredParams`: `[{"type": "public-key", "alg": -7}, {"type": "public-key", "alg": -257}]` (`ES256` P-256 and `RS256`)
   - `timeout`: `60000`
   - `authenticatorSelection`: `{ "userVerification": "required", "residentKey": "preferred" }`
   - `attestation`: `"none"` (privacy-preserving; does not track hardware batch certificates unless needed)

### 3.2 Step B — Verify Attestation (`POST /api/v1/evaluators/passkeys/register/verify`)
1. **Parse `clientDataJSON`:**
   - Verify `clientData.type == "webauthn.create"`.
   - Extract `clientData.challenge` and atomically fetch & lock the matching unconsumed row in `public.webauthn_challenges` where `user_id = current_user.id`, `purpose = 'registration'`, `consumed_at IS NULL`, and `expires_at > now()`.
   - If missing, expired, or already consumed → reject with `HTTP 400` (`code="webauthn_invalid_or_expired_challenge"`).
   - Verify `clientData.origin` is in `settings.WEBAUTHN_EXPECTED_ORIGINS`.
2. **Parse `attestationObject` & `authData`:**
   - Verify `authData.rpIdHash == SHA256(rp_id.encode("utf-8"))`.
   - Verify `UP` (User Present, bit 0) is `1` and `UV` (User Verified, bit 2) is `1`.
   - Verify `AT` (Attested Credential Data Present, bit 6) is `1`.
   - Extract `credential_id`, COSE `credential_public_key`, `sign_count`, and `aaguid`.
   - Verify COSE key algorithm is in allowed algorithms (`-7` ES256 or `-257` RS256).
3. **Persist & Consume Challenge:**
   - Mark challenge consumed (`consumed_at = now()`).
   - Insert into `public.webauthn_credentials` (`user_id`, `credential_id`, `public_key`, `sign_count`, `transports`, `device_name`, `user_verified_on_register=True`).
   - Also update `public.users.webauthn_credential_id` and `public.users.webauthn_public_key` if currently `NULL` (for backward compatibility with legacy schema readers).
   - Append `evaluator.passkey_registered` to `public.audit_logs`.

---

## 4. Passkey Authentication & Inspection Submission Flow (`navigator.credentials.get()`)

```mermaid
sequenceDiagram
    autonumber
    actor Eval as Approved Evaluator
    participant Browser as Browser WebAuthn API
    participant API as FastAPI Backend
    participant DB as Supabase PostgreSQL

    Eval->>API: POST /api/v1/evaluators/passkeys/authenticate/options { purpose: "inspection_submit", task_id }
    API->>DB: Verify user.role='evaluator', evaluator_status='approved', task ownership & cooldown
    API->>DB: INSERT webauthn_challenges (purpose='inspection_submit', operation_context={task_id}, TTL=5m)
    API-->>Eval: PublicKeyCredentialRequestOptionsJSON (challenge, allowCredentials, userVerification='required')
    Eval->>Browser: navigator.credentials.get({ publicKey })
    Browser->>Eval: Local OS Biometric / PIN Prompt (Fingerprint / Face / Windows Hello)
    Browser-->>Eval: PublicKeyCredential (authenticatorData, clientDataJSON, signature, credentialId)
    Eval->>API: POST /api/v1/evaluators/inspections/submit (Checklist + Photos + WebAuthn Assertion + Idempotency-Key)
    API->>DB: Atomically consume challenge (WHERE challenge=:c AND user_id=:u AND purpose='inspection_submit' AND consumed_at IS NULL AND expires_at > now())
    API->>DB: Load active credential (WHERE credential_id=:cred AND user_id=:u AND revoked_at IS NULL)
    API->>API: Verify origin, rpIdHash, UP=1, UV=1, cryptographic signature over (authData || SHA256(clientDataJSON)), and sign_count > stored_sign_count
    API->>DB: Update credential sign_count & last_used_at; save inspection; record audit_log
    API-->>Eval: 201 Created (Inspection Submitted & Verified)
```

### 4.1 Strict Verification Checks Performed on Every Assertion
1. **Challenge Binding & Replay Prevention:**
   - The challenge must exist in `public.webauthn_challenges`, belong to `current_user.id`, match the exact `purpose` (`authentication` or `inspection_submit`), match `operation_context.task_id` (for inspection submissions), have `consumed_at IS NULL`, and have `expires_at > now()`.
   - Consumed immediately in a single atomic transaction so concurrent or replayed requests fail with `HTTP 401` (`code="webauthn_challenge_replayed_or_expired"`).
2. **Credential Ownership & Revocation Check:**
   - Lookup `credential_id` in `public.webauthn_credentials`.
   - Must exist, have `user_id == current_user.id` (prevents cross-account credential substitution), and have `revoked_at IS NULL` (rejects revoked credentials with `HTTP 401`, `code="webauthn_credential_revoked"`).
3. **Origin & RP ID Hash Verification:**
   - `clientDataJSON.type == "webauthn.get"`
   - `clientDataJSON.origin` in `WEBAUTHN_EXPECTED_ORIGINS`
   - `authenticatorData.rpIdHash == SHA256(WEBAUTHN_RP_ID)`
4. **User Presence (`UP`) & User Verification (`UV`) Flags:**
   - Both `UP` (bit 0) and `UV` (bit 2) in `authenticatorData.flags` **must be `1`**. Assertions without biometric/PIN user verification (`UV == 0`) are rejected with `HTTP 403` (`code="webauthn_user_verification_required"`).
5. **Cryptographic Signature Verification:**
   - Reconstruct verification data: `signed_bytes = authenticator_data_bytes + hashlib.sha256(client_data_json_bytes).digest()`.
   - Verify the ECDSA P-256 (`ES256`) or RSA (`RS256`) signature over `signed_bytes` using the stored COSE `public_key`.
6. **Sign Counter (`sign_count`) Clone Detection & Legacy Counter Calibration:**
   - **Native Credentials (`sign_count_initialized = true`):**
     - If either stored `sign_count > 0` or assertion `sign_count > 0`, require `assertion.sign_count > stored.sign_count`.
     - If `assertion.sign_count <= stored.sign_count`, reject the assertion (`code="webauthn_sign_count_anomaly"`), flag a potential cloned authenticator in `public.audit_logs`, and block submission.
   - **Migrated Legacy Credentials (`migration_source = 'legacy_users_table'`, `sign_count_initialized = false`):**
     - Because `users.webauthn_credential_id` / `users.webauthn_public_key` did not store a signature counter, a migrated credential starts with `sign_count_initialized = false`.
     - On the first assertion from a migrated credential:
       1. Verify that `public_key` is a valid, parseable COSE key (ES256 `-7` or RS256 `-257`). If unparseable or invalid, reject with `HTTP 409 Conflict` (`code="webauthn_legacy_re_registration_required"`) and instruct the evaluator to register a fresh passkey.
       2. Verify the challenge, origin, `rpIdHash`, `UP=1`, `UV=1`, and cryptographic signature over `authenticatorData || SHA256(clientDataJSON)`.
       3. Calibrate and initialize the counter baseline: `SET sign_count = assertion.sign_count, sign_count_initialized = true, last_used_at = now()` and append `evaluator.legacy_passkey_calibrated` to `public.audit_logs`.
       4. All subsequent assertions on that credential enforce strict monotonic progression (`assertion.sign_count > stored.sign_count`).
   - Update `webauthn_credentials.sign_count = assertion.sign_count` and `last_used_at = now()`.

---

## 5. Multi-Device Support, Credential Revocation & Fallback Policy

1. **Multiple Passkeys per Evaluator:**
   - Evaluators may register multiple authenticators (e.g. primary Android phone + backup hardware security key or secondary phone) so a damaged phone does not permanently lock out their account after admin verification.
2. **Credential Revocation (`DELETE /api/v1/evaluators/passkeys/{credential_id}`):**
   - Evaluators (for their own credentials) or Admins (for any evaluator credential) can revoke a passkey.
   - Sets `revoked_at = now()`, `revoked_by = actor_id`, and writes an `evaluator.passkey_revoked` audit record. Revoked credentials are immediately excluded from `allowCredentials` and rejected during verification.
3. **Fallback Policy When WebAuthn Is Unavailable:**
   - If the evaluator's browser or device does not support `window.PublicKeyCredential`, the UI clearly explains that a WebAuthn-capable device/browser (Chrome/Edge/Safari/Firefox over HTTPS or `localhost` with screen lock/biometrics enabled) is required to submit field inspections.
   - **Strict Security Rule:** Neither the frontend nor the backend ever permits a "demo simulation toggle" or fake passkey bypass to unlock inspection submission.

