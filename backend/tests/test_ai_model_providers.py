"""Comprehensive tests for Groq & OpenRouter AI model provider architecture,
separate domain services, strict Pydantic validation, privacy guards on `:free`
endpoints, retry/error handling, and deterministic business rule preservation.

OWNER: Ibrahim
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.openrouter import (
    ComplaintUnderstandingService,
    GroqConfigError,
    GroqHttpClient,
    GroqProviderError,
    GroqResponseValidationError,
    GroqTimeoutError,
    ImageInspectionAnalysisService,
    ImageValidationError,
    MaintenanceEmailDraftingService,
    OpenRouterHttpClient,
    OpenRouterPrivacyViolationError,
    OpenRouterResponseValidationError,
    SpeechTranscriptionService,
    enforce_openrouter_privacy_guard,
    is_free_openrouter_model,
    validate_image_upload,
)
from app.modules.openrouter.pipeline import validate_audio_upload
from app.modules.openrouter.schemas import (
    ComplaintSentiment,
    DataSensitivityClassification,
    InspectionImageDefect,
    StructuredComplaintAnalysis,
    StructuredImageInspectionAnalysis,
    StructuredMaintenanceEmailDraft,
    VoiceIssueCategory,
)


def _make_test_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "OPENROUTER_API_KEY": "sk-or-test-default",
        "OPENROUTER_API_KEY_VL": "sk-or-test-vl",
        "OPENROUTER_API_KEY_ULTRA": "sk-or-test-ultra",
        "OPENROUTER_API_KEY_LIGHTNING": "sk-or-test-lightning",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "AUDIO_TRANSCRIPTION_MODEL": "deepgram/nova-3",
        "COMPLAINT_ANALYSIS_MODEL": "google/gemini-3.8-flash",
        "OPENROUTER_MULTIMODAL_MODEL": "nvidia/nemotron-3.5-super-vl:free",
        "OPENROUTER_REASONING_MODEL": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "OPENROUTER_FAST_EXTRACTION_MODEL": "nvidia/nemotron-3.5-lightning:free",
        "OPENROUTER_TIMEOUT_SECONDS": 5.0,
        "OPENROUTER_MAX_RETRIES": 2,
        "OPENROUTER_RETRY_BACKOFF_SECONDS": 0.01,
        "OPENROUTER_ALLOW_FREE_MODEL_SENSITIVE_DATA": False,
        "GROQ_API_KEY": "gsk_test_groq_key",
        "GROQ_BASE_URL": "https://api.groq.com/openai/v1",
        "GROQ_STT_PRIMARY_MODEL": "whisper-large-v3-turbo",
        "GROQ_STT_FALLBACK_MODEL": "whisper-large-v3",
        "GROQ_TIMEOUT_SECONDS": 5.0,
        "GROQ_MAX_RETRIES": 2,
        "GROQ_RETRY_BACKOFF_SECONDS": 0.01,
        "AI_STT_PROVIDER": "openrouter",
        "AI_COMPLAINT_MODEL_TIER": "legacy",
        "AI_EMAIL_DRAFT_MODEL_TIER": "reasoning",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# 1. Groq Speech-to-Text Client & Accuracy Fallback Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_groq_missing_api_key_raises_config_error() -> None:
    client = GroqHttpClient(settings=_make_test_settings(GROQ_API_KEY=""))
    audio = validate_audio_upload(b"RIFF1234WAVE", filename="clip.wav")
    with pytest.raises(GroqConfigError) as exc_info:
        await client.transcribe_audio(audio)
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "groq_not_configured"


@pytest.mark.anyio
async def test_groq_primary_transcription_and_verbose_json_parsing() -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={
                "text": "ಶೌಚಾಲಯದಲ್ಲಿ ನೀರು ಬರುತ್ತಿಲ್ಲ ಮತ್ತು ನೆಲ ಕೊಳಕಾಗಿದೆ.",
                "language": "kn",
                "duration": 5.1,
            },
        )

    client = GroqHttpClient(
        settings=_make_test_settings(), transport=httpx.MockTransport(handler)
    )
    audio = validate_audio_upload(b"RIFF1234WAVE", filename="kannada.m4a")
    res = await client.transcribe_audio(audio, language="kn")

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert str(req.url) == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert req.headers["Authorization"] == "Bearer gsk_test_groq_key"
    raw_body = req.content.decode("latin-1")
    assert "whisper-large-v3-turbo" in raw_body
    assert "verbose_json" in raw_body

    assert res.text == "ಶೌಚಾಲಯದಲ್ಲಿ ನೀರು ಬರುತ್ತಿಲ್ಲ ಮತ್ತು ನೆಲ ಕೊಳಕಾಗಿದೆ."
    assert res.model == "whisper-large-v3-turbo"
    assert res.language == "kn"
    assert res.duration_seconds == 5.1
    assert res.usage is not None
    assert res.usage.seconds == 5.1


@pytest.mark.anyio
async def test_groq_automatic_accuracy_fallback_to_whisper_large_v3() -> None:
    """When `whisper-large-v3-turbo` fails or returns an empty/noisy transcript,
    `transcribe_with_accuracy_fallback` automatically retries with `whisper-large-v3`.
    """
    models_called: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw_body = request.content.decode("latin-1")
        if "whisper-large-v3-turbo" in raw_body:
            models_called.append("whisper-large-v3-turbo")
            # Simulate primary turbo returning empty transcript on heavy noise
            return httpx.Response(200, json={"text": " ", "duration": 2.0})
        models_called.append("whisper-large-v3")
        return httpx.Response(
            200,
            json={
                "text": "The toilet door lock is broken and there is no water.",
                "language": "en",
                "duration": 3.8,
            },
        )

    client = GroqHttpClient(
        settings=_make_test_settings(), transport=httpx.MockTransport(handler)
    )
    audio = validate_audio_upload(b"RIFF1234WAVE", filename="noisy_clip.wav")
    result = await client.transcribe_with_accuracy_fallback(audio)

    assert models_called == ["whisper-large-v3-turbo", "whisper-large-v3"]
    assert result.model == "whisper-large-v3"
    assert result.text == "The toilet door lock is broken and there is no water."


@pytest.mark.anyio
async def test_groq_timeout_and_rate_limit_errors() -> None:
    audio = validate_audio_upload(b"RIFF1234WAVE", filename="clip.wav")

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Groq read timeout", request=request)

    client_timeout = GroqHttpClient(
        settings=_make_test_settings(), transport=httpx.MockTransport(timeout_handler)
    )
    with pytest.raises(GroqTimeoutError) as t_exc:
        await client_timeout.transcribe_audio(audio)
    assert t_exc.value.status_code == 504
    assert t_exc.value.code == "groq_timeout"

    def rate_limit_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Rate limit reached"}})

    client_429 = GroqHttpClient(
        settings=_make_test_settings(),
        transport=httpx.MockTransport(rate_limit_handler),
    )
    with pytest.raises(GroqProviderError) as r_exc:
        await client_429.transcribe_audio(audio)
    assert r_exc.value.status_code == 429
    assert r_exc.value.code == "groq_rate_limited"

    def invalid_json_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": 123})

    client_bad = GroqHttpClient(
        settings=_make_test_settings(),
        transport=httpx.MockTransport(invalid_json_handler),
    )
    with pytest.raises(GroqResponseValidationError):
        await client_bad.transcribe_audio(audio)


# ---------------------------------------------------------------------------
# 2. Privacy Guard Tests on `:free` OpenRouter Endpoints
# ---------------------------------------------------------------------------


def test_free_openrouter_endpoint_privacy_guard_blocks_sensitive_classifications() -> None:
    assert is_free_openrouter_model("nvidia/nemotron-3.5-super-vl:free") is True
    assert is_free_openrouter_model("nvidia/nemotron-3-ultra-550b-a55b:free") is True
    assert is_free_openrouter_model("nvidia/nemotron-3.5-lightning:free") is True
    assert is_free_openrouter_model("google/gemini-3.8-flash") is False

    # 1. Government ID documents MUST be blocked on `:free` endpoints
    with pytest.raises(OpenRouterPrivacyViolationError, match="government_id_document"):
        enforce_openrouter_privacy_guard(
            "nvidia/nemotron-3.5-super-vl:free",
            sensitivity=DataSensitivityClassification.GOVERNMENT_ID_DOCUMENT,
        )

    # 2. Personal identity information MUST be blocked on `:free` endpoints
    with pytest.raises(OpenRouterPrivacyViolationError, match="personal_identity_info"):
        enforce_openrouter_privacy_guard(
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            sensitivity=DataSensitivityClassification.PERSONAL_IDENTITY_INFO,
        )

    # 3. Raw citizen voice recordings MUST be blocked on `:free` endpoints
    with pytest.raises(OpenRouterPrivacyViolationError, match="raw_citizen_voice"):
        enforce_openrouter_privacy_guard(
            "nvidia/nemotron-3.5-lightning:free",
            sensitivity=DataSensitivityClassification.RAW_CITIZEN_VOICE,
        )

    # 4. Private identifiable inspection photos MUST be blocked on `:free` endpoints
    with pytest.raises(
        OpenRouterPrivacyViolationError,
        match="private_identifiable_inspection_photo",
    ):
        enforce_openrouter_privacy_guard(
            "nvidia/nemotron-3.5-super-vl:free",
            sensitivity=DataSensitivityClassification.PRIVATE_IDENTIFIABLE_INSPECTION_PHOTO,
        )

    # 5. Embedded Aadhaar / phone / email in text payload MUST be blocked on `:free` endpoints
    with pytest.raises(OpenRouterPrivacyViolationError, match="aadhaar_number"):
        enforce_openrouter_privacy_guard(
            "nvidia/nemotron-3.5-lightning:free",
            sensitivity=DataSensitivityClassification.ANONYMIZED_TEST_DATA,
            text_content="Evaluator Aadhaar is 4567 8901 2345 at Indiranagar toilet",
        )

    with pytest.raises(OpenRouterPrivacyViolationError, match="indian_phone"):
        enforce_openrouter_privacy_guard(
            "nvidia/nemotron-3.5-lightning:free",
            sensitivity=DataSensitivityClassification.ANONYMIZED_TEST_DATA,
            text_content="Call me at +91 9876543210 regarding this washroom",
        )

    # 6. Anonymized test data passes cleanly
    enforce_openrouter_privacy_guard(
        "nvidia/nemotron-3.5-lightning:free",
        sensitivity=DataSensitivityClassification.ANONYMIZED_TEST_DATA,
        text_content="Water tap is leaking and the floor is wet in stall 2.",
    )


# ---------------------------------------------------------------------------
# 3. Separate Services & Strict Pydantic Validation Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_speech_transcription_service_preserves_openrouter_default_and_supports_groq() -> None:
    def or_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"text": "OpenRouter transcription output", "model": "deepgram/nova-3"},
        )

    def groq_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "text": "Groq turbo transcription output",
                "duration": 2.4,
                "language": "en",
            },
        )

    settings = _make_test_settings(AI_STT_PROVIDER="openrouter")
    or_client = OpenRouterHttpClient(
        settings=settings, transport=httpx.MockTransport(or_handler)
    )
    groq_client = GroqHttpClient(
        settings=settings, transport=httpx.MockTransport(groq_handler)
    )
    stt_service = SpeechTranscriptionService(
        openrouter_client=or_client, groq_client=groq_client, settings=settings
    )
    audio = validate_audio_upload(b"RIFF1234WAVE", filename="sample.wav")

    # Default uses OpenRouter (`deepgram/nova-3`)
    default_res = await stt_service.transcribe(audio)
    assert default_res.model == "deepgram/nova-3"

    # Explicit override routes to Groq (`whisper-large-v3-turbo`)
    groq_res = await stt_service.transcribe(audio, provider_override="groq")
    assert groq_res.model == "whisper-large-v3-turbo"
    assert groq_res.text == "Groq turbo transcription output"


@pytest.mark.anyio
async def test_complaint_understanding_service_with_nemotron_fast_extraction() -> None:
    captured_models: list[str] = []
    captured_auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_auth.append(request.headers["Authorization"])
        body = json.loads(request.content.decode("utf-8"))
        captured_models.append(body["model"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "is_complaint": True,
                                    "sentiment": "negative",
                                    "primary_category": "water",
                                    "extracted_categories": ["water", "odor"],
                                    "urgency_score": 4,
                                    "summary": "No water supply and strong foul smell.",
                                    "moderation_status": "clean",
                                    "moderation_reason": None,
                                    "confidence": 0.92,
                                }
                            ),
                        }
                    }
                ]
            },
        )

    settings = _make_test_settings()
    or_client = OpenRouterHttpClient(
        settings=settings, transport=httpx.MockTransport(handler)
    )
    svc = ComplaintUnderstandingService(openrouter_client=or_client, settings=settings)

    # Test with Nemotron 3.5 Lightning override
    result = await svc.understand_complaint(
        "पाणी नहीं आ रहा है और बहुत बदबू है।",
        model_override="nvidia/nemotron-3.5-lightning:free",
        sensitivity=DataSensitivityClassification.ANONYMIZED_TEST_DATA,
    )
    assert captured_models == ["nvidia/nemotron-3.5-lightning:free"]
    assert captured_auth == ["Bearer sk-or-test-lightning"]
    assert result.is_complaint is True
    assert result.sentiment == ComplaintSentiment.NEGATIVE
    assert result.primary_category == VoiceIssueCategory.WATER
    assert result.extracted_categories == [
        VoiceIssueCategory.WATER,
        VoiceIssueCategory.ODOR,
    ]


@pytest.mark.anyio
async def test_image_inspection_analysis_service_multimodal_and_privacy_enforcement() -> None:
    captured_auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_auth.append(request.headers["Authorization"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "is_washroom_image": True,
                                    "contains_identifiable_person_or_id": False,
                                    "visual_cleanliness_band": "dirty",
                                    "detected_defects": [
                                        "floor_soiling",
                                        "standing_water",
                                        "floor_soiling",
                                    ],
                                    "water_fixture_visible": True,
                                    "lighting_adequate": True,
                                    "summary": "Wet floor with visible muddy footprints near stall.",
                                    "confidence": 0.89,
                                }
                            ),
                        }
                    }
                ]
            },
        )

    settings = _make_test_settings()
    or_client = OpenRouterHttpClient(
        settings=settings, transport=httpx.MockTransport(handler)
    )
    img_svc = ImageInspectionAnalysisService(
        openrouter_client=or_client, settings=settings
    )

    # 1. Valid anonymized test image succeeds and enforces advisory invariants
    anon_image = validate_image_upload(
        b"\x89PNG\r\n\x1a\nsynthetic_image_bytes",
        mime_type="image/png",
        sensitivity=DataSensitivityClassification.ANONYMIZED_TEST_DATA,
    )
    analysis = await img_svc.analyze_image(
        anon_image, facility_context="Synthetic stall inspection"
    )
    assert captured_auth == ["Bearer sk-or-test-vl"]
    assert analysis.is_washroom_image is True
    assert analysis.visual_cleanliness_band == "dirty"
    assert analysis.detected_defects == [
        InspectionImageDefect.FLOOR_SOILING,
        InspectionImageDefect.STANDING_WATER,
    ]
    # Invariant: AI never modifies scores, approvals, payouts, or availability
    assert analysis.advisory_only is True
    assert analysis.official_score_modified is False
    assert analysis.evaluator_approval_modified is False
    assert analysis.payment_amount_modified is False
    assert analysis.availability_state_modified is False

    # 2. Government ID image MUST be blocked before making any network request
    gov_id_image = validate_image_upload(
        b"\x89PNG\r\n\x1a\ngov_id_bytes",
        mime_type="image/png",
        sensitivity=DataSensitivityClassification.GOVERNMENT_ID_DOCUMENT,
    )
    with pytest.raises(OpenRouterPrivacyViolationError):
        await img_svc.analyze_image(gov_id_image)
    assert len(captured_auth) == 1  # No 2nd network call was made


@pytest.mark.anyio
async def test_maintenance_email_drafting_service_and_deterministic_fallback() -> None:
    def failing_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Upstream model overloaded")

    settings = _make_test_settings()
    or_client = OpenRouterHttpClient(
        settings=settings, transport=httpx.MockTransport(failing_handler)
    )
    email_svc = MaintenanceEmailDraftingService(
        openrouter_client=or_client, settings=settings
    )

    context = {
        "facility_name": "Indiranagar Metro Public Washroom",
        "ward": "Hoysala Nagar Ward 80",
        "issue_type": "feedback_cleanliness_alert",
        "summary": "4 negative cleanliness votes in 60-minute window.",
        "triage_level": "escalated",
    }

    # With fallback_on_error=True, returns deterministic Python draft when LLM fails
    draft = await email_svc.draft_email(context, fallback_on_error=True)
    assert "[Namma Suvidha]" in draft.subject
    assert draft.urgency_label == "urgent"
    assert len(draft.action_items) == 3
    assert draft.advisory_only is True
    assert draft.official_score_modified is False
    assert draft.evaluator_approval_modified is False
    assert draft.payment_amount_modified is False
    assert draft.availability_state_modified is False


def test_strict_pydantic_schemas_reject_unauthorized_score_or_payout_mutation_fields() -> None:
    """Verify `extra="forbid"` blocks any LLM attempt to inject score/payout/approval mutations."""
    with pytest.raises(ValidationError):
        StructuredComplaintAnalysis.model_validate(
            {
                "is_complaint": True,
                "sentiment": "negative",
                "primary_category": "water",
                "extracted_categories": ["water"],
                "urgency_score": 4,
                "summary": "No water",
                "moderation_status": "clean",
                "confidence": 0.9,
                "new_facility_score": 10.0,  # Forbidden extra field
            }
        )

    with pytest.raises(ValidationError):
        StructuredImageInspectionAnalysis.model_validate(
            {
                "is_washroom_image": True,
                "visual_cleanliness_band": "clean",
                "detected_defects": [],
                "summary": "Clean floor",
                "official_score_modified": True,  # Forbidden Literal[False] violation
            }
        )

    with pytest.raises(ValidationError):
        StructuredMaintenanceEmailDraft.model_validate(
            {
                "subject": "Maintenance Alert",
                "salutation": "Dear Supervisor,",
                "executive_summary": "Water leak detected in stall 1.",
                "action_items": ["Fix pipe"],
                "urgency_label": "urgent",
                "closing": "Regards",
                "payment_amount_modified": True,  # Forbidden Literal[False] violation
            }
        )


def test_image_upload_validation_rejects_empty_oversized_and_bad_mime() -> None:
    with pytest.raises(ImageValidationError, match="must not be empty"):
        validate_image_upload(b"")

    with pytest.raises(ImageValidationError, match="exceeds max"):
        validate_image_upload(b"x" * 200, max_bytes=100)

    with pytest.raises(ImageValidationError, match="Unsupported image MIME type"):
        validate_image_upload(b"1234", mime_type="application/pdf")

