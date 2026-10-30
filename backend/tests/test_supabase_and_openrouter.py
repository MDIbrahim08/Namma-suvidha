"""Automated tests for Supabase database health and OpenRouter Voice Feedback Pipeline.

OWNER: Ibrahim
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.session import check_database_connection, get_engine, get_sessionmaker
from app.modules.openrouter.client import (
    OpenRouterConfigError,
    OpenRouterHttpClient,
    OpenRouterProviderError,
    OpenRouterResponseValidationError,
    OpenRouterTimeoutError,
)
from app.modules.openrouter.pipeline import (
    AudioValidationError,
    VoiceFeedbackPipelineService,
    classify_moderation,
    extract_issue_categories,
    validate_audio_upload,
    validate_structured_complaint_json,
    validate_transcript,
)
from app.modules.openrouter.schemas import (
    ComplaintSentiment,
    ModerationClassification,
    VoiceIssueCategory,
)

# ---------------------------------------------------------------------------
# 1. Database Configuration & Supabase Connection Tests
# ---------------------------------------------------------------------------


def test_settings_normalizes_postgresql_url_to_psycopg() -> None:
    s1 = Settings(
        DATABASE_URL="postgresql://postgres.ref:secret@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
    )
    assert (
        s1.DATABASE_URL
        == "postgresql+psycopg://postgres.ref:secret@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
    )

    s2 = Settings(
        DATABASE_URL="postgres://postgres.ref:secret@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
    )
    assert (
        s2.DATABASE_URL
        == "postgresql+psycopg://postgres.ref:secret@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
    )


def test_missing_database_url_handled_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    try:
        status = check_database_connection()
        assert status["connected"] is False
        assert status["postgis_available"] is False
        assert status["error"] is not None
        assert "DATABASE_URL is not configured" in status["error"]
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_invalid_database_url_handled_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://invalid_user:wrong@127.0.0.1:59999/nonexistent",
    )
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    try:
        status = check_database_connection()
        assert status["connected"] is False
        assert status["error"] is not None
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_configured_supabase_database_connection(client: TestClient) -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    configured_url = get_settings().DATABASE_URL
    if not configured_url or "localhost" in configured_url:
        pytest.skip("Supabase DATABASE_URL not configured in environment")

    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["postgis_available"] is True
    assert body["postgis_version"] is not None


# ---------------------------------------------------------------------------
# 2. OpenRouter Configuration & Client Tests (Mocked HTTP Transport)
# ---------------------------------------------------------------------------


def _make_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "OPENROUTER_API_KEY": "sk-or-test-key",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "AUDIO_TRANSCRIPTION_MODEL": "deepgram/nova-3",
        "COMPLAINT_ANALYSIS_MODEL": "google/gemini-3.8-flash",
        "OPENROUTER_TIMEOUT_SECONDS": 5.0,
        "VOICE_MAX_AUDIO_BYTES": 1024 * 1024,
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.anyio
async def test_openrouter_missing_api_key_raises_config_error() -> None:
    settings = _make_settings(OPENROUTER_API_KEY="")
    client = OpenRouterHttpClient(settings=settings)
    audio = validate_audio_upload(b"RIFF....WAVEfmt ", filename="sample.wav")

    with pytest.raises(OpenRouterConfigError) as exc_info:
        await client.transcribe_audio(audio)
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "openrouter_not_configured"


@pytest.mark.anyio
async def test_openrouter_transcription_parsing_and_request_contract() -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={
                "text": "There is no water in the tap and the floor is dirty.",
                "model": "deepgram/nova-3",
                "language": "en",
                "duration": 4.2,
                "usage": {
                    "total_tokens": 95,
                    "input_tokens": 75,
                    "output_tokens": 20,
                    "cost": 0.00031,
                },
            },
        )

    transport = httpx.MockTransport(handler)
    client = OpenRouterHttpClient(settings=_make_settings(), transport=transport)
    audio = validate_audio_upload(b"RIFF1234WAVE", content_type="audio/wav")

    result = await client.transcribe_audio(audio, language="en")

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert str(req.url) == "https://openrouter.ai/api/v1/audio/transcriptions"
    assert req.headers["Authorization"] == "Bearer sk-or-test-key"
    body = json.loads(req.content.decode("utf-8"))
    assert body["model"] == "deepgram/nova-3"
    assert body["input_audio"]["format"] == "wav"
    assert body["input_audio"]["data"] == audio.base64_data

    assert result.text == "There is no water in the tap and the floor is dirty."
    assert result.model == "deepgram/nova-3"
    assert result.language == "en"
    assert result.duration_seconds == 4.2
    assert result.usage is not None
    assert result.usage.total_tokens == 95


@pytest.mark.anyio
async def test_openrouter_structured_complaint_analysis_parsing() -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "gen-123",
                "model": "google/gemini-3.8-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "is_complaint": True,
                                    "sentiment": "negative",
                                    "primary_category": "water",
                                    "extracted_categories": [
                                        "water",
                                        "cleanliness",
                                        "water",
                                    ],
                                    "urgency_score": 4,
                                    "summary": "No running water in taps and floor is dirty.",
                                    "moderation_status": "clean",
                                    "moderation_reason": None,
                                    "confidence": 0.94,
                                }
                            ),
                        },
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    client = OpenRouterHttpClient(settings=_make_settings(), transport=transport)

    analysis = await client.analyze_complaint(
        "There is no water in the tap and the floor is dirty."
    )

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert str(req.url) == "https://openrouter.ai/api/v1/chat/completions"
    req_body = json.loads(req.content.decode("utf-8"))
    assert req_body["model"] == "google/gemini-3.8-flash"
    assert req_body["response_format"] == {"type": "json_object"}

    assert analysis.is_complaint is True
    assert analysis.sentiment == ComplaintSentiment.NEGATIVE
    assert analysis.primary_category == VoiceIssueCategory.WATER
    assert analysis.extracted_categories == [
        VoiceIssueCategory.WATER,
        VoiceIssueCategory.CLEANLINESS,
    ]
    assert analysis.urgency_score == 4
    assert analysis.moderation_status == ModerationClassification.CLEAN


@pytest.mark.anyio
async def test_openrouter_provider_errors_and_timeouts() -> None:
    # 1. Timeout
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timed out reading from OpenRouter", request=request)

    client_timeout = OpenRouterHttpClient(
        settings=_make_settings(), transport=httpx.MockTransport(timeout_handler)
    )
    audio = validate_audio_upload(b"audio-bytes", explicit_format="mp3")
    with pytest.raises(OpenRouterTimeoutError) as timeout_exc:
        await client_timeout.transcribe_audio(audio)
    assert timeout_exc.value.status_code == 504
    assert timeout_exc.value.code == "openrouter_timeout"

    # 2. HTTP 429 Rate Limit
    def rate_limit_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Rate limit exceeded"}})

    client_429 = OpenRouterHttpClient(
        settings=_make_settings(), transport=httpx.MockTransport(rate_limit_handler)
    )
    with pytest.raises(OpenRouterProviderError) as rl_exc:
        await client_429.transcribe_audio(audio)
    assert rl_exc.value.status_code == 429
    assert rl_exc.value.code == "openrouter_rate_limited"

    # 3. HTTP 502/503 Upstream Error
    def server_error_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    client_503 = OpenRouterHttpClient(
        settings=_make_settings(), transport=httpx.MockTransport(server_error_handler)
    )
    with pytest.raises(OpenRouterProviderError) as srv_exc:
        await client_503.analyze_complaint("Water is leaking")
    assert srv_exc.value.status_code == 502
    assert srv_exc.value.code == "openrouter_upstream_error"

    # 4. Malformed JSON response
    def malformed_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "not-valid-json"}}
                ]
            },
        )

    client_malformed = OpenRouterHttpClient(
        settings=_make_settings(), transport=httpx.MockTransport(malformed_handler)
    )
    with pytest.raises(OpenRouterResponseValidationError):
        await client_malformed.analyze_complaint("Water is leaking")


# ---------------------------------------------------------------------------
# 3. Voice Feedback Pipeline Preparation & Invariant Tests
# ---------------------------------------------------------------------------


def test_audio_upload_validation_rules() -> None:
    with pytest.raises(AudioValidationError, match="must not be empty"):
        validate_audio_upload(b"", filename="clip.wav")

    with pytest.raises(AudioValidationError, match="exceeds max"):
        validate_audio_upload(b"x" * 200, filename="clip.wav", max_bytes=100)

    with pytest.raises(AudioValidationError, match="Unsupported audio format"):
        validate_audio_upload(b"valid-bytes", explicit_format="exe")

    valid = validate_audio_upload(b"valid-bytes", content_type="audio/webm;codecs=opus")
    assert valid.audio_format == "webm"
    assert valid.size_bytes == 11


def test_transcript_validation_rules() -> None:
    empty = validate_transcript("   \n\t  ")
    assert empty.is_usable is False
    assert empty.rejection_reason == "transcript_empty"

    noise = validate_transcript("... !!! ???")
    assert noise.is_usable is False
    assert noise.rejection_reason == "transcript_non_alphanumeric_noise"

    usable = validate_transcript("  Tap   is broken and leaking water. ")
    assert usable.is_usable is True
    assert usable.normalized_text == "Tap is broken and leaking water."
    assert usable.word_count == 6


def test_structured_json_validation_and_moderation_helpers() -> None:
    analysis = validate_structured_complaint_json(
        {
            "is_complaint": True,
            "sentiment": "negative",
            "primary_category": "plumbing",
            "extracted_categories": ["water", "plumbing", "odor"],
            "urgency_score": 5,
            "summary": "Broken pipe flooding the stall.",
            "moderation_status": "clean",
            "moderation_reason": None,
            "confidence": 0.91,
        }
    )
    categories = extract_issue_categories(analysis)
    assert categories == [
        VoiceIssueCategory.PLUMBING,
        VoiceIssueCategory.WATER,
        VoiceIssueCategory.ODOR,
    ]
    mod_status, actionable = classify_moderation(analysis)
    assert mod_status == ModerationClassification.CLEAN
    assert actionable is True

    spam_analysis = analysis.model_copy(
        update={
            "moderation_status": ModerationClassification.SPAM,
            "moderation_reason": "Promotional audio",
        }
    )
    _, spam_actionable = classify_moderation(spam_analysis)
    assert spam_actionable is False


@pytest.mark.anyio
async def test_voice_pipeline_keeps_yes_no_vote_independent_and_single_vote_weight() -> None:
    """Verify:
    - Multiple extracted categories still result in citizen_vote_count == 1.
    - Original YES/NO vote remains recorded even when OpenRouter fails or rejects transcript.
    - Model output never directly modifies official scores or maintenance statuses.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(
                200,
                json={
                    "text": "The door latch is broken, there is no water, and the light is out.",
                    "model": "deepgram/nova-3",
                },
            )
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
                                    "primary_category": "locked",
                                    "extracted_categories": [
                                        "locked",
                                        "water",
                                        "lighting",
                                    ],
                                    "urgency_score": 4,
                                    "summary": "Latch broken, no water, and lighting out.",
                                    "moderation_status": "clean",
                                    "moderation_reason": None,
                                    "confidence": 0.96,
                                }
                            ),
                        }
                    }
                ]
            },
        )

    client = OpenRouterHttpClient(
        settings=_make_settings(), transport=httpx.MockTransport(handler)
    )
    pipeline = VoiceFeedbackPipelineService(client=client)

    result = await pipeline.process_submission(
        facility_id="fac-001",
        is_clean_vote=False,
        audio_bytes=b"RIFF....WAVEfmt ",
        filename="feedback.wav",
    )

    assert result.cleanliness_vote_recorded is True
    assert result.is_clean_vote is False
    # 3 categories extracted, but citizen_vote_count MUST remain 1
    assert result.analysis is not None
    assert len(result.analysis.extracted_categories) == 3
    assert result.citizen_vote_count == 1
    # Never modifies official scores or maintenance statuses directly
    assert result.advisory_only is True
    assert result.official_score_modified is False
    assert result.maintenance_status_modified is False

    # Now simulate a total OpenRouter failure: YES/NO vote MUST still be preserved
    def failing_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Upstream down")

    failing_pipeline = VoiceFeedbackPipelineService(
        client=OpenRouterHttpClient(
            settings=_make_settings(), transport=httpx.MockTransport(failing_handler)
        )
    )
    failed_voice_result = await failing_pipeline.process_submission(
        facility_id="fac-001",
        is_clean_vote=True,
        audio_bytes=b"RIFF....WAVEfmt ",
        filename="feedback.wav",
    )
    assert failed_voice_result.cleanliness_vote_recorded is True
    assert failed_voice_result.is_clean_vote is True
    assert failed_voice_result.citizen_vote_count == 1
    assert failed_voice_result.analysis is None
    assert failed_voice_result.voice_error is not None
