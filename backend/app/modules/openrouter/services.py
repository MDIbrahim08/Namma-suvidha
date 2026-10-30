"""Dedicated AI Services for Namma Suvidha:
1. `SpeechTranscriptionService` — Groq (`whisper-large-v3-turbo` + `whisper-large-v3` fallback)
   or OpenRouter (`deepgram/nova-3`).
2. `ComplaintUnderstandingService` — OpenRouter structured complaint classification & extraction
   (`google/gemini-3.8-flash` default, configurable to `nvidia/nemotron-3.5-lightning:free`
   or `nvidia/nemotron-3-ultra-550b-a55b:free`).
3. `ImageInspectionAnalysisService` — OpenRouter multimodal inspection image analysis
   (`nvidia/nemotron-3.5-super-vl:free` default) with strict privacy guards.
4. `MaintenanceEmailDraftingService` — OpenRouter reasoning email drafting
   (`nvidia/nemotron-3-ultra-550b-a55b:free` default) with deterministic fallback.

OWNER: Ibrahim

Invariants Enforced Across All Services:
- AI responses are strictly validated with Pydantic `extra="forbid"` schemas.
- AI outputs NEVER directly modify facility scores, evaluator approvals, payment amounts,
  or availability states (`advisory_only=True`).
- Free OpenRouter endpoints (`:free`) are blocked from receiving government ID documents,
  personal identity information, raw citizen voice recordings, or identifiable private
  inspection photos.
"""

from __future__ import annotations

import base64
from typing import Any, Literal

from app.core.config import Settings, get_settings
from app.modules.openrouter.client import (
    OpenRouterClientProtocol,
    OpenRouterError,
    OpenRouterHttpClient,
    enforce_openrouter_privacy_guard,
)
from app.modules.openrouter.groq_client import (
    GroqClientProtocol,
    GroqHttpClient,
)
from app.modules.openrouter.pipeline import (
    extract_issue_categories,
    validate_transcript,
)
from app.modules.openrouter.schemas import (
    SUPPORTED_IMAGE_MIME_TYPES,
    DataSensitivityClassification,
    StructuredComplaintAnalysis,
    StructuredImageInspectionAnalysis,
    StructuredMaintenanceEmailDraft,
    TranscriptionResult,
    ValidatedAudioInput,
    ValidatedImageInput,
    ValidatedTranscript,
)


class ImageValidationError(ValueError):
    """Raised when an inspection image payload is empty, oversized, or unsupported."""


def validate_image_upload(
    image_bytes: bytes,
    *,
    mime_type: str = "image/png",
    sensitivity: DataSensitivityClassification = (
        DataSensitivityClassification.ANONYMIZED_TEST_DATA
    ),
    max_bytes: int | None = None,
) -> ValidatedImageInput:
    """Validate image payload size and MIME type, returning a frozen `ValidatedImageInput`."""
    if not isinstance(image_bytes, bytes) or len(image_bytes) == 0:
        raise ImageValidationError("Image payload must not be empty.")

    limit = max_bytes if max_bytes is not None else get_settings().IMAGE_MAX_BYTES
    if len(image_bytes) > limit:
        raise ImageValidationError(
            f"Image payload size ({len(image_bytes)} bytes) exceeds max ({limit} bytes)."
        )

    normalized_mime = mime_type.split(";")[0].strip().lower()
    if normalized_mime not in SUPPORTED_IMAGE_MIME_TYPES:
        raise ImageValidationError(
            f"Unsupported image MIME type '{mime_type}'. "
            f"Supported: {sorted(SUPPORTED_IMAGE_MIME_TYPES)}"
        )

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_uri = f"data:{normalized_mime};base64,{b64}"
    return ValidatedImageInput(
        mime_type=normalized_mime,  # type: ignore[arg-type]
        size_bytes=len(image_bytes),
        base64_data=b64,
        data_uri=data_uri,
        sensitivity=sensitivity,
    )


class SpeechTranscriptionService:
    """1. Dedicated service for speech-to-text transcription.

    Supports both:
    - OpenRouter (`deepgram/nova-3`, preserved production default)
    - Groq (`whisper-large-v3-turbo` with automatic accuracy fallback to `whisper-large-v3`)
    """

    def __init__(
        self,
        *,
        openrouter_client: OpenRouterClientProtocol | None = None,
        groq_client: GroqClientProtocol | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._openrouter = openrouter_client or OpenRouterHttpClient(
            settings=self._settings
        )
        self._groq = groq_client or GroqHttpClient(settings=self._settings)

    async def transcribe(
        self,
        audio: ValidatedAudioInput,
        *,
        language: str | None = None,
        provider_override: Literal["openrouter", "groq"] | None = None,
        use_groq_accuracy_fallback: bool = True,
    ) -> TranscriptionResult:
        provider = provider_override or self._settings.AI_STT_PROVIDER
        if provider == "groq":
            if use_groq_accuracy_fallback:
                return await self._groq.transcribe_with_accuracy_fallback(
                    audio, language=language
                )
            return await self._groq.transcribe_audio(audio, language=language)
        return await self._openrouter.transcribe_audio(audio, language=language)


class ComplaintUnderstandingService:
    """2. Dedicated service for structured citizen complaint classification & category extraction."""

    def __init__(
        self,
        *,
        openrouter_client: OpenRouterClientProtocol | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._openrouter = openrouter_client or OpenRouterHttpClient(
            settings=self._settings
        )

    async def understand_complaint(
        self,
        transcript: str | ValidatedTranscript,
        *,
        model_override: str | None = None,
        sensitivity: DataSensitivityClassification = (
            DataSensitivityClassification.ANONYMIZED_TEST_DATA
        ),
    ) -> StructuredComplaintAnalysis:
        validated = (
            transcript
            if isinstance(transcript, ValidatedTranscript)
            else validate_transcript(transcript)
        )
        if not validated.is_usable:
            raise ValueError(
                f"Cannot classify unusable transcript (reason={validated.rejection_reason})."
            )

        analysis = await self._openrouter.analyze_complaint(
            validated.normalized_text,
            model_override=model_override,
            sensitivity=sensitivity,
        )
        merged_categories = extract_issue_categories(analysis)
        return analysis.model_copy(update={"extracted_categories": merged_categories})


class ImageInspectionAnalysisService:
    """3. Dedicated service for multimodal toilet inspection image analysis.

    Uses `OPENROUTER_MULTIMODAL_MODEL` (`nvidia/nemotron-3.5-super-vl:free` by default)
    and enforces privacy guards so government IDs or private identifiable photos are
    never transmitted to free OpenRouter endpoints.
    """

    def __init__(
        self,
        *,
        openrouter_client: OpenRouterClientProtocol | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._openrouter = openrouter_client or OpenRouterHttpClient(
            settings=self._settings
        )

    async def analyze_image(
        self,
        image: ValidatedImageInput,
        *,
        facility_context: str | None = None,
        model_override: str | None = None,
    ) -> StructuredImageInspectionAnalysis:
        target_model = (
            model_override or self._settings.OPENROUTER_MULTIMODAL_MODEL
        ).strip()
        enforce_openrouter_privacy_guard(
            target_model,
            sensitivity=image.sensitivity,
            text_content=facility_context,
            allow_override=self._settings.OPENROUTER_ALLOW_FREE_MODEL_SENSITIVE_DATA,
        )
        result = await self._openrouter.analyze_inspection_image(
            image,
            facility_context=facility_context,
            model_override=target_model,
        )
        return result


class MaintenanceEmailDraftingService:
    """4. Dedicated service for structured maintenance alert email drafting.

    Uses `OPENROUTER_REASONING_MODEL` (`nvidia/nemotron-3-ultra-550b-a55b:free` by default)
    and provides a deterministic Python fallback if the AI provider is unavailable or
    rate-limited, ensuring operator alerts are never blocked by LLM outages.
    """

    def __init__(
        self,
        *,
        openrouter_client: OpenRouterClientProtocol | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._openrouter = openrouter_client or OpenRouterHttpClient(
            settings=self._settings
        )

    @staticmethod
    def build_deterministic_draft(
        issue_context: dict[str, Any],
    ) -> StructuredMaintenanceEmailDraft:
        """Deterministic Python business rule fallback for maintenance alert emails."""
        facility_name = str(issue_context.get("facility_name") or "Public Washroom")
        ward = str(issue_context.get("ward") or "Assigned Ward")
        issue_type = str(issue_context.get("issue_type") or "maintenance").replace(
            "_", " "
        )
        summary = str(
            issue_context.get("summary")
            or "Actionable sanitation or maintenance issue detected via citizen/inspector telemetry."
        )
        triage = str(issue_context.get("triage_level") or "priority").lower()
        urgency: Literal["routine", "priority", "urgent", "critical"] = "priority"
        if triage in ("critical", "escalated", "high"):
            urgency = "urgent"
        elif triage in ("low", "routine"):
            urgency = "routine"

        return StructuredMaintenanceEmailDraft(
            subject=f"[Namma Suvidha] {issue_type.upper()} Alert — {facility_name} ({ward})",
            salutation="Dear Ward Sanitation Supervisor,",
            executive_summary=(
                f"Facility '{facility_name}' in {ward} requires {urgency} attention: {summary}"
            )[:600],
            action_items=[
                f"Dispatch maintenance/cleaning staff to {facility_name} ({ward}).",
                "Inspect water supply, floor cleanliness, lighting, and door locks.",
                "Acknowledge and update issue status in the Namma Suvidha Government Portal.",
            ],
            urgency_label=urgency,
            closing="Regards, Namma Suvidha Automated Monitoring System",
        )

    async def draft_email(
        self,
        issue_context: dict[str, Any],
        *,
        model_override: str | None = None,
        sensitivity: DataSensitivityClassification = (
            DataSensitivityClassification.ANONYMIZED_TEST_DATA
        ),
        fallback_on_error: bool = False,
    ) -> StructuredMaintenanceEmailDraft:
        target_model = (
            model_override or self._settings.OPENROUTER_REASONING_MODEL
        ).strip()
        try:
            return await self._openrouter.draft_maintenance_email(
                issue_context,
                model_override=target_model,
                sensitivity=sensitivity,
            )
        except OpenRouterError:
            if fallback_on_error:
                return self.build_deterministic_draft(issue_context)
            raise

