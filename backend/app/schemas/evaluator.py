"""Typed Pydantic v2 request/response schemas for `/api/v1/evaluator` and
`/api/v1/evaluator/admin` endpoints.

OWNER: Ibrahim
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.evaluator.enums import (
    IDDocumentType,
    WebAuthnChallengePurpose,
)


class EvaluatorRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=2, max_length=120)
    phone: str = Field(..., min_length=8, max_length=24)
    operating_area: str = Field(..., min_length=2, max_length=150)
    preferred_language: str = Field(default="en", min_length=2, max_length=32)


class EvaluatorPasskeyRegisterOptionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str | None = None


class EvaluatorPasskeyRegisterVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: str = Field(..., min_length=4)
    client_data_json_b64: str = Field(..., min_length=4)
    authenticator_data_b64: str = Field(..., min_length=4)
    public_key_b64: str | None = None
    transports: list[str] = Field(default_factory=lambda: ["internal"])
    device_name: str = Field(default="Registered Passkey", max_length=120)


class EvaluatorPasskeyAuthOptionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: WebAuthnChallengePurpose = WebAuthnChallengePurpose.AUTHENTICATION
    task_id: str | None = None
    origin: str | None = None


class EvaluatorPasskeyAuthVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: str = Field(..., min_length=4)
    client_data_json_b64: str = Field(..., min_length=4)
    authenticator_data_b64: str = Field(..., min_length=4)
    signature_b64: str = Field(..., min_length=4)
    purpose: WebAuthnChallengePurpose = WebAuthnChallengePurpose.AUTHENTICATION
    task_id: str | None = None


class EvaluatorDocumentBase64UploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: IDDocumentType
    file_base64: str = Field(..., min_length=4)
    mime_type: str | None = None


class EvaluatorInspectionSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., min_length=1)
    checklist_answers: dict[str, Any]
    evidence_urls: list[str] = Field(default_factory=list)
    notes: str | None = None
    idempotency_key: str | None = None
    # Mandatory WebAuthn cryptographic assertion fields
    credential_id: str | None = None
    client_data_json_b64: str | None = None
    authenticator_data_b64: str | None = None
    signature_b64: str | None = None


class AdminApproveEvaluatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = None


class AdminReasonRequiredRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=500)

