"""OpenRouter HTTP client for dedicated audio transcription and structured complaint analysis.

OWNER: Ibrahim

Endpoints used against `https://openrouter.ai/api/v1`:
1. `POST /audio/transcriptions` — speech-to-text (`deepgram/nova-3`).
2. `POST /chat/completions` — structured complaint extraction (`google/gemini-3.8-flash`).
"""

import asyncio
import json
import logging
import re
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.modules.openrouter.schemas import (
    FORBIDDEN_FREE_ENDPOINT_CLASSIFICATIONS,
     DataSensitivityClassification,
    StructuredComplaintAnalysis,
    StructuredImageInspectionAnalysis,
    StructuredMaintenanceEmailDraft,
    TranscriptionResult,
    TranscriptionUsage,
    ValidatedAudioInput,
    ValidatedImageInput,
)

logger = logging.getLogger("namma_suvidha.openrouter")

# Heuristic PII patterns blocked from being sent to `:free` OpenRouter endpoints
_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aadhaar_number", re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")),
    ("pan_number", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("email_address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("indian_phone", re.compile(r"(?:\+91[-\s]?)?[6-9]\d{9}\b")),
)


class OpenRouterError(Exception):
    """Base exception for OpenRouter configuration, network, or payload errors."""

    def __init__(self, status_code: int, detail: str, code: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


class OpenRouterConfigError(OpenRouterError):
    def __init__(
        self,
        detail: str = "OPENROUTER_API_KEY is not configured in the backend environment.",
    ) -> None:
        super().__init__(
            status_code=503, detail=detail, code="openrouter_not_configured"
        )


class OpenRouterTimeoutError(OpenRouterError):
    def __init__(
        self,
        detail: str = "OpenRouter AI request timed out.",
    ) -> None:
        super().__init__(status_code=504, detail=detail, code="openrouter_timeout")


class OpenRouterProviderError(OpenRouterError):
    def __init__(
        self,
        detail: str = "OpenRouter provider returned an upstream error.",
        status_code: int = 502,
        code: str = "openrouter_provider_error",
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, code=code)


class OpenRouterResponseValidationError(OpenRouterError):
    def __init__(
        self,
        detail: str = "OpenRouter returned a malformed or unparseable JSON response.",
    ) -> None:
        super().__init__(
            status_code=502, detail=detail, code="openrouter_invalid_response"
        )


class OpenRouterPrivacyViolationError(OpenRouterError):
    """Raised when sensitive/identifiable data is blocked from free OpenRouter endpoints."""

    def __init__(
        self,
        detail: str = (
            "Privacy guard blocked sending sensitive or identifiable data to a free "
            "OpenRouter endpoint."
        ),
    ) -> None:
        super().__init__(
            status_code=400, detail=detail, code="openrouter_privacy_violation"
        )


def is_free_openrouter_model(model_id: str) -> bool:
    """Return True if the OpenRouter model identifier targets a `:free` tier endpoint."""
    return model_id.strip().lower().endswith(":free")


def enforce_openrouter_privacy_guard(
    model_id: str,
    *,
    sensitivity: DataSensitivityClassification = (
        DataSensitivityClassification.ANONYMIZED_TEST_DATA
    ),
    text_content: str | None = None,
    allow_override: bool = False,
) -> None:
    """Enforce the critical privacy restriction on `:free` OpenRouter endpoints:
    Never send government ID documents, personal identity information, raw citizen
    voice recordings, or identifiable private inspection photos to free endpoints.
    """
    if allow_override or not is_free_openrouter_model(model_id):
        return

    if sensitivity in FORBIDDEN_FREE_ENDPOINT_CLASSIFICATIONS:
        raise OpenRouterPrivacyViolationError(
            f"Cannot send data classified as '{sensitivity.value}' to free OpenRouter "
            f"model '{model_id}'."
        )

    if text_content:
        for pattern_name, pattern in _PII_PATTERNS:
            if pattern.search(text_content):
                raise OpenRouterPrivacyViolationError(
                    f"Detected potential PII ({pattern_name}) in text payload targeting "
                    f"free OpenRouter model '{model_id}'."
                )


class OpenRouterClientProtocol(Protocol):
    async def transcribe_audio(
        self,
        audio: ValidatedAudioInput,
        language: str | None = None,
    ) -> TranscriptionResult: ...

    async def analyze_complaint(
        self,
        transcript_text: str,
        *,
        model_override: str | None = None,
        sensitivity: DataSensitivityClassification = (
            DataSensitivityClassification.ANONYMIZED_TEST_DATA
        ),
    ) -> StructuredComplaintAnalysis: ...

    async def analyze_inspection_image(
        self,
        image: ValidatedImageInput,
        *,
        facility_context: str | None = None,
        model_override: str | None = None,
    ) -> StructuredImageInspectionAnalysis: ...

    async def draft_maintenance_email(
        self,
        issue_context: dict[str, Any],
        *,
        model_override: str | None = None,
        sensitivity: DataSensitivityClassification = (
            DataSensitivityClassification.ANONYMIZED_TEST_DATA
        ),
    ) -> StructuredMaintenanceEmailDraft: ...


SYSTEM_PROMPT_COMPLAINT_ANALYSIS = (
    "You are the public sanitation complaint analyzer for Namma Suvidha. "
    "Analyze the citizen's transcribed voice feedback about a public toilet facility and "
    "return ONLY a valid JSON object matching the exact schema:\n"
    "{\n"
    '  "is_complaint": boolean,\n'
    '  "sentiment": "positive" | "neutral" | "negative",\n'
    '  "primary_category": "cleanliness" | "water" | "odor" | "lighting" | "locked" | '
    '"plumbing" | "supplies" | "accessibility" | "safety" | "other",\n'
    '  "extracted_categories": [array of unique categories from the same enum],\n'
    '  "urgency_score": integer 1 to 5,\n'
    '  "summary": "concise factual summary",\n'
    '  "moderation_status": "clean" | "spam" | "abuse" | "gibberish",\n'
    '  "moderation_reason": string or null,\n'
    '  "confidence": float 0.0 to 1.0\n'
    "}"
)

SYSTEM_PROMPT_IMAGE_INSPECTION = (
    "You are the visual sanitation inspection analyzer for Namma Suvidha. "
    "Inspect the provided public washroom image and return ONLY a valid JSON object "
    "matching the exact schema:\n"
    "{\n"
    '  "is_washroom_image": boolean,\n'
    '  "contains_identifiable_person_or_id": boolean,\n'
    '  "visual_cleanliness_band": "clean" | "moderate" | "dirty" | "unusable",\n'
    '  "detected_defects": [array of unique values from: "floor_soiling", '
    '"toilet_bowl_staining", "standing_water", "broken_fixture", "missing_water_tap", '
    '"poor_lighting", "door_lock_damage", "overflowing_bin", "graffiti_or_vandalism", '
    '"none_observed"],\n'
    '  "water_fixture_visible": boolean,\n'
    '  "lighting_adequate": boolean,\n'
    '  "summary": "concise factual summary of visual condition",\n'
    '  "confidence": float 0.0 to 1.0\n'
    "}"
)

SYSTEM_PROMPT_EMAIL_DRAFTING = (
    "You are the civic sanitation notification drafting assistant for Namma Suvidha. "
    "Given anonymized facility maintenance issue telemetry, draft a structured alert "
    "email for the ward maintenance supervisor. Return ONLY a valid JSON object matching "
    "the exact schema:\n"
    "{\n"
    '  "subject": "concise alert subject line (5-200 chars)",\n'
    '  "salutation": "formal greeting",\n'
    '  "executive_summary": "factual summary of the sanitation issue (10-600 chars)",\n'
    '  "action_items": ["1 to 10 concrete maintenance action items"],\n'
    '  "urgency_label": "routine" | "priority" | "urgent" | "critical",\n'
    '  "closing": "formal sign-off"\n'
    "}"
)


class OpenRouterHttpClient:
    """Reusable async OpenRouter client reading settings from environment variables."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport

    @property
    def base_url(self) -> str:
        url = (self._settings.OPENROUTER_BASE_URL or "").strip().rstrip("/")
        if not url:
            raise OpenRouterConfigError("OPENROUTER_BASE_URL must not be empty.")
        return url

    @property
    def api_key(self) -> str:
        key = (self._settings.OPENROUTER_API_KEY or "").strip()
        if not key:
            raise OpenRouterConfigError(
                "OPENROUTER_API_KEY is missing. Set it in backend/.env before calling OpenRouter."
            )
        return key

    @property
    def audio_transcription_model(self) -> str:
        model = (self._settings.AUDIO_TRANSCRIPTION_MODEL or "").strip()
        if not model:
            raise OpenRouterConfigError("AUDIO_TRANSCRIPTION_MODEL must not be empty.")
        return model

    @property
    def complaint_analysis_model(self) -> str:
        tier = getattr(self._settings, "AI_COMPLAINT_MODEL_TIER", "legacy")
        if tier == "fast_extraction":
            model = (self._settings.OPENROUTER_FAST_EXTRACTION_MODEL or "").strip()
        elif tier == "reasoning":
            model = (self._settings.OPENROUTER_REASONING_MODEL or "").strip()
        else:
            model = (self._settings.COMPLAINT_ANALYSIS_MODEL or "").strip()
        if not model:
            raise OpenRouterConfigError("COMPLAINT_ANALYSIS_MODEL must not be empty.")
        return model

    @property
    def multimodal_model(self) -> str:
        model = (self._settings.OPENROUTER_MULTIMODAL_MODEL or "").strip()
        if not model:
            raise OpenRouterConfigError("OPENROUTER_MULTIMODAL_MODEL must not be empty.")
        return model

    @property
    def reasoning_model(self) -> str:
        model = (self._settings.OPENROUTER_REASONING_MODEL or "").strip()
        if not model:
            raise OpenRouterConfigError("OPENROUTER_REASONING_MODEL must not be empty.")
        return model

    @property
    def fast_extraction_model(self) -> str:
        model = (self._settings.OPENROUTER_FAST_EXTRACTION_MODEL or "").strip()
        if not model:
            raise OpenRouterConfigError(
                "OPENROUTER_FAST_EXTRACTION_MODEL must not be empty."
            )
        return model

    def resolve_api_key_for_model(self, model_id: str | None = None) -> str:
        """Resolve model-specific OpenRouter key if configured, else fallback to OPENROUTER_API_KEY."""
        m = (model_id or "").lower()
        if "super-vl" in m or "-vl" in m:
            vl_key = (getattr(self._settings, "OPENROUTER_API_KEY_VL", "") or "").strip()
            if vl_key:
                return vl_key
        if "ultra" in m:
            ultra_key = (
                getattr(self._settings, "OPENROUTER_API_KEY_ULTRA", "") or ""
            ).strip()
            if ultra_key:
                return ultra_key
        if "lightning" in m or "nano" in m or "super" in m:
            fast_key = (
                getattr(self._settings, "OPENROUTER_API_KEY_LIGHTNING", "") or ""
            ).strip()
            if fast_key:
                return fast_key
        return self.api_key

    def _headers(self, api_key_override: str | None = None) -> dict[str, str]:
        token = api_key_override or self.api_key
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "HTTP-Referer": "https://namma-suvidha.local",
            "X-Title": self._settings.APP_NAME,
        }

    async def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        api_key_override: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        max_retries = max(0, int(getattr(self._settings, "OPENROUTER_MAX_RETRIES", 0)))
        backoff_base = float(
            getattr(self._settings, "OPENROUTER_RETRY_BACKOFF_SECONDS", 0.5)
        )
        headers = self._headers(api_key_override=api_key_override)

        response: httpx.Response | None = None
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self._settings.OPENROUTER_TIMEOUT_SECONDS),
                    transport=self._transport,
                    headers=headers,
                ) as client:
                    response = await client.post(url, json=payload)
            except httpx.TimeoutException as exc:
                if attempt < max_retries and self._transport is None:
                    await asyncio.sleep(backoff_base * (2**attempt))
                    continue
                logger.warning("OpenRouter request timed out for %s", path)
                raise OpenRouterTimeoutError(
                    f"OpenRouter request to {path} timed out after "
                    f"{self._settings.OPENROUTER_TIMEOUT_SECONDS}s."
                ) from exc
            except httpx.RequestError as exc:
                if attempt < max_retries and self._transport is None:
                    await asyncio.sleep(backoff_base * (2**attempt))
                    continue
                logger.warning(
                    "OpenRouter network error for %s: %s", path, type(exc).__name__
                )
                raise OpenRouterProviderError(
                    f"Network error communicating with OpenRouter ({type(exc).__name__})."
                ) from exc

            if response.status_code in (429, 502, 503, 504) and (
                attempt < max_retries and self._transport is None
            ):
                await asyncio.sleep(backoff_base * (2**attempt))
                continue
            break

        assert response is not None
        if response.status_code == 429:
            raise OpenRouterProviderError(
                detail="OpenRouter rate limit exceeded (HTTP 429).",
                status_code=429,
                code="openrouter_rate_limited",
            )

        if response.status_code >= 500:
            raise OpenRouterProviderError(
                detail=f"OpenRouter upstream server error (HTTP {response.status_code}).",
                status_code=502,
                code="openrouter_upstream_error",
            )

        if response.status_code >= 400:
            detail_msg = f"OpenRouter rejected request with HTTP {response.status_code}."
            try:
                err_body = response.json()
                if isinstance(err_body, dict) and isinstance(err_body.get("error"), dict):
                    upstream_msg = err_body["error"].get("message")
                    if upstream_msg:
                        detail_msg = f"{detail_msg} ({upstream_msg})"
            except ValueError:
                pass
            raise OpenRouterProviderError(
                detail=detail_msg,
                status_code=502,
                code="openrouter_request_rejected",
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise OpenRouterResponseValidationError(
                "OpenRouter returned non-JSON body."
            ) from exc

        if not isinstance(data, dict):
            raise OpenRouterResponseValidationError(
                "OpenRouter response root must be a JSON object."
            )
        if "error" in data and data["error"]:
            err_obj = data["error"]
            msg = (
                err_obj.get("message", str(err_obj))
                if isinstance(err_obj, dict)
                else str(err_obj)
            )
            raise OpenRouterProviderError(
                detail=f"OpenRouter provider error: {msg}",
                status_code=502,
                code="openrouter_provider_error",
            )
        return data

    def _extract_chat_json(self, data: dict[str, Any]) -> dict[str, Any]:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenRouterResponseValidationError(
                "OpenRouter chat completion response is missing 'choices'."
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise OpenRouterResponseValidationError(
                "OpenRouter choice entry is malformed."
            )
        message = first_choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            # Some reasoning models return reasoning_content if content is empty
            raise OpenRouterResponseValidationError(
                "OpenRouter chat completion message content is empty or non-string."
            )

        cleaned = _strip_markdown_json_fence(content.strip())
        try:
            parsed_json = json.loads(cleaned)
        except ValueError as exc:
            raise OpenRouterResponseValidationError(
                "Model output is not valid JSON."
            ) from exc
        if not isinstance(parsed_json, dict):
            raise OpenRouterResponseValidationError(
                "Model JSON output must be a JSON object."
            )
        return parsed_json

    async def transcribe_audio(
        self,
        audio: ValidatedAudioInput,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Call OpenRouter's dedicated `POST /audio/transcriptions` endpoint."""
        model_id = self.audio_transcription_model
        enforce_openrouter_privacy_guard(
            model_id,
            sensitivity=DataSensitivityClassification.RAW_CITIZEN_VOICE,
            allow_override=bool(
                getattr(
                    self._settings, "OPENROUTER_ALLOW_FREE_MODEL_SENSITIVE_DATA", False
                )
            ),
        )
        payload: dict[str, Any] = {
            "model": model_id,
            "input_audio": {
                "data": audio.base64_data,
                "format": audio.audio_format,
            },
            "response_format": "json",
        }
        if language:
            payload["language"] = language

        key = self.resolve_api_key_for_model(model_id)
        data = await self._post_json(
            "/audio/transcriptions", payload, api_key_override=key
        )
        text = data.get("text")
        if not isinstance(text, str):
            raise OpenRouterResponseValidationError(
                "OpenRouter transcription response is missing string field 'text'."
            )

        usage_raw = data.get("usage")
        usage = (
            TranscriptionUsage.model_validate(usage_raw)
            if isinstance(usage_raw, dict)
            else None
        )
        duration = data.get("duration")
        duration_seconds = (
            float(duration) if isinstance(duration, int | float) else None
        )

        return TranscriptionResult(
            text=text,
            model=str(data.get("model") or model_id),
            language=data.get("language")
            if isinstance(data.get("language"), str)
            else language,
            duration_seconds=duration_seconds,
            usage=usage,
        )

    async def analyze_complaint(
        self,
        transcript_text: str,
        *,
        model_override: str | None = None,
        sensitivity: DataSensitivityClassification = (
            DataSensitivityClassification.ANONYMIZED_TEST_DATA
        ),
    ) -> StructuredComplaintAnalysis:
        """Call OpenRouter's `POST /chat/completions` for structured complaint extraction."""
        model_id = (model_override or self.complaint_analysis_model).strip()
        enforce_openrouter_privacy_guard(
            model_id,
            sensitivity=sensitivity,
            text_content=transcript_text,
            allow_override=bool(
                getattr(
                    self._settings, "OPENROUTER_ALLOW_FREE_MODEL_SENSITIVE_DATA", False
                )
            ),
        )
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_COMPLAINT_ANALYSIS},
                {"role": "user", "content": transcript_text},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }
        key = self.resolve_api_key_for_model(model_id)
        data = await self._post_json(
            "/chat/completions", payload, api_key_override=key
        )
        parsed_json = self._extract_chat_json(data)

        try:
            return StructuredComplaintAnalysis.model_validate(parsed_json)
        except ValidationError as exc:
            first_msg = exc.errors()[0]["msg"]
            raise OpenRouterResponseValidationError(
                f"Model JSON failed StructuredComplaintAnalysis validation: {first_msg}"
            ) from exc

    async def analyze_inspection_image(
        self,
        image: ValidatedImageInput,
        *,
        facility_context: str | None = None,
        model_override: str | None = None,
    ) -> StructuredImageInspectionAnalysis:
        """Call OpenRouter's multimodal model (`nvidia/nemotron-3.5-super-vl:free` by default)
        for washroom image inspection analysis.
        """
        model_id = (model_override or self.multimodal_model).strip()
        enforce_openrouter_privacy_guard(
            model_id,
            sensitivity=image.sensitivity,
            text_content=facility_context,
            allow_override=bool(
                getattr(
                    self._settings, "OPENROUTER_ALLOW_FREE_MODEL_SENSITIVE_DATA", False
                )
            ),
        )
        prompt_text = (
            "Inspect this anonymized public washroom image and return the JSON assessment."
            if not facility_context
            else f"Facility context: {facility_context}\nReturn the JSON assessment."
        )
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_IMAGE_INSPECTION},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": image.data_uri},
                        },
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }
        key = self.resolve_api_key_for_model(model_id)
        data = await self._post_json(
            "/chat/completions", payload, api_key_override=key
        )
        parsed_json = self._extract_chat_json(data)

        try:
            return StructuredImageInspectionAnalysis.model_validate(parsed_json)
        except ValidationError as exc:
            first_msg = exc.errors()[0]["msg"]
            raise OpenRouterResponseValidationError(
                f"Model JSON failed StructuredImageInspectionAnalysis validation: {first_msg}"
            ) from exc

    async def draft_maintenance_email(
        self,
        issue_context: dict[str, Any],
        *,
        model_override: str | None = None,
        sensitivity: DataSensitivityClassification = (
            DataSensitivityClassification.ANONYMIZED_TEST_DATA
        ),
    ) -> StructuredMaintenanceEmailDraft:
        """Call OpenRouter's reasoning model (`nvidia/nemotron-3-ultra-550b-a55b:free` by default)
        to draft a structured operator maintenance alert email.
        """
        model_id = (model_override or self.reasoning_model).strip()
        serialized_context = json.dumps(issue_context, ensure_ascii=False)
        enforce_openrouter_privacy_guard(
            model_id,
            sensitivity=sensitivity,
            text_content=serialized_context,
            allow_override=bool(
                getattr(
                    self._settings, "OPENROUTER_ALLOW_FREE_MODEL_SENSITIVE_DATA", False
                )
            ),
        )
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_EMAIL_DRAFTING},
                {"role": "user", "content": serialized_context},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }
        key = self.resolve_api_key_for_model(model_id)
        data = await self._post_json(
            "/chat/completions", payload, api_key_override=key
        )
        parsed_json = self._extract_chat_json(data)

        try:
            return StructuredMaintenanceEmailDraft.model_validate(parsed_json)
        except ValidationError as exc:
            first_msg = exc.errors()[0]["msg"]
            raise OpenRouterResponseValidationError(
                f"Model JSON failed StructuredMaintenanceEmailDraft validation: {first_msg}"
            ) from exc


def _strip_markdown_json_fence(raw: str) -> str:
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return raw
