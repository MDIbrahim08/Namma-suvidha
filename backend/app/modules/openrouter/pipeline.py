"""Modular Voice Feedback Pipeline services and validators.

OWNER: Ibrahim

Implements the 7 required pipeline stages:
1. Audio upload validation (`validate_audio_upload`)
2. Speech transcription (`transcribe_speech`)
3. Transcript validation (`validate_transcript`)
4. Complaint classification (`classify_complaint`)
5. Issue category extraction (`extract_issue_categories`)
6. Abuse and spam classification (`classify_moderation`)
7. Structured JSON validation (`validate_structured_complaint_json`)

Critical Invariants Enforced:
- The citizen's original YES/NO cleanliness vote (`is_clean`) is recorded and preserved
  independently of whether voice transcription or AI analysis succeeds or fails.
- Multiple extracted issue categories from a single voice clip still count as a single citizen vote
  (`citizen_vote_count == 1`).
- AI model output is strictly advisory (`advisory_only == True`, `official_score_modified == False`,
  `maintenance_status_modified == False`).
"""

import base64
import json
import re
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.modules.openrouter.client import (
    OpenRouterClientProtocol,
    OpenRouterError,
    OpenRouterResponseValidationError,
)
from app.modules.openrouter.schemas import (
    MIME_TYPE_TO_AUDIO_FORMAT,
    SUPPORTED_AUDIO_FORMATS,
    ModerationClassification,
    StructuredComplaintAnalysis,
    TranscriptionResult,
    ValidatedAudioInput,
    ValidatedTranscript,
    VoiceFeedbackPipelineResult,
    VoiceIssueCategory,
)


class AudioValidationError(ValueError):
    """Raised when an uploaded audio clip is empty, too large, or in an unsupported format."""


def resolve_audio_format(
    filename: str | None = None,
    content_type: str | None = None,
    explicit_format: str | None = None,
) -> str:
    """Resolve and validate the audio format for OpenRouter `input_audio.format`."""
    if explicit_format:
        fmt = explicit_format.strip().lower().lstrip(".")
        if fmt in SUPPORTED_AUDIO_FORMATS:
            return fmt
        supported_str = sorted(SUPPORTED_AUDIO_FORMATS)
        raise AudioValidationError(
            f"Unsupported audio format '{explicit_format}'. Supported: {supported_str}"
        )

    if content_type:
        mime = content_type.split(";")[0].strip().lower()
        if mime in MIME_TYPE_TO_AUDIO_FORMAT:
            return MIME_TYPE_TO_AUDIO_FORMAT[mime]

    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].strip().lower()
        if ext in SUPPORTED_AUDIO_FORMATS:
            return ext

    raise AudioValidationError(
        f"Unable to determine supported audio format from filename={filename!r} "
        f"or content_type={content_type!r}. Supported: {sorted(SUPPORTED_AUDIO_FORMATS)}"
    )


def validate_audio_upload(
    audio_bytes: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    explicit_format: str | None = None,
    max_bytes: int | None = None,
) -> ValidatedAudioInput:
    """1. Audio upload validation: checks non-empty, size cap, format, and encodes base64."""
    if not isinstance(audio_bytes, bytes) or len(audio_bytes) == 0:
        raise AudioValidationError("Audio payload must not be empty.")

    limit = max_bytes if max_bytes is not None else get_settings().VOICE_MAX_AUDIO_BYTES
    if len(audio_bytes) > limit:
        raise AudioValidationError(
            f"Audio payload size ({len(audio_bytes)} bytes) exceeds max ({limit} bytes)."
        )

    audio_format = resolve_audio_format(
        filename=filename,
        content_type=content_type,
        explicit_format=explicit_format,
    )
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    return ValidatedAudioInput(
        audio_format=audio_format,  # type: ignore[arg-type]
        size_bytes=len(audio_bytes),
        base64_data=encoded,
    )


def validate_transcript(
    raw_text: str,
    *,
    min_chars: int = 2,
    max_chars: int = 4000,
) -> ValidatedTranscript:
    """3. Transcript validation: normalizes whitespace and rejects empty/noise transcripts."""
    normalized = re.sub(r"\s+", " ", (raw_text or "")).strip()
    if not normalized:
        return ValidatedTranscript(
            raw_text=raw_text or "",
            normalized_text="",
            word_count=0,
            is_usable=False,
            rejection_reason="transcript_empty",
        )

    if len(normalized) < min_chars:
        return ValidatedTranscript(
            raw_text=raw_text,
            normalized_text=normalized,
            word_count=len(normalized.split()),
            is_usable=False,
            rejection_reason="transcript_too_short",
        )

    if len(normalized) > max_chars:
        normalized = normalized[:max_chars].strip()

    # Check that there is at least one alphanumeric or Indic script character
    if not any(ch.isalnum() for ch in normalized):
        return ValidatedTranscript(
            raw_text=raw_text,
            normalized_text=normalized,
            word_count=0,
            is_usable=False,
            rejection_reason="transcript_non_alphanumeric_noise",
        )

    words = normalized.split()
    return ValidatedTranscript(
        raw_text=raw_text,
        normalized_text=normalized,
        word_count=len(words),
        is_usable=True,
        rejection_reason=None,
    )


def validate_structured_complaint_json(
    raw_payload: str | dict[str, Any],
) -> StructuredComplaintAnalysis:
    """7. Structured JSON validation: parses and strictly validates LLM complaint output."""
    if isinstance(raw_payload, str):
        try:
            data = json.loads(raw_payload)
        except ValueError as exc:
            raise OpenRouterResponseValidationError(
                "Complaint analysis payload is not valid JSON."
            ) from exc
    elif isinstance(raw_payload, dict):
        data = raw_payload
    else:
        raise OpenRouterResponseValidationError(
            "Complaint analysis payload must be a JSON string or dict."
        )

    try:
        return StructuredComplaintAnalysis.model_validate(data)
    except ValidationError as exc:
        raise OpenRouterResponseValidationError(
            f"Structured complaint JSON failed schema validation: {exc.errors()[0]['msg']}"
        ) from exc


def extract_issue_categories(
    analysis: StructuredComplaintAnalysis,
) -> list[VoiceIssueCategory]:
    """5. Issue category extraction: returns deduplicated categories with primary first."""
    ordered: list[VoiceIssueCategory] = [analysis.primary_category]
    for category in analysis.extracted_categories:
        if category not in ordered:
            ordered.append(category)
    return ordered


def classify_moderation(
    analysis: StructuredComplaintAnalysis,
) -> tuple[ModerationClassification, bool]:
    """6. Abuse and spam classification: returns `(moderation_status, is_actionable_complaint)`."""
    is_actionable = (
        analysis.moderation_status == ModerationClassification.CLEAN
        and analysis.is_complaint
    )
    return analysis.moderation_status, is_actionable


class VoiceFeedbackPipelineService:
    """Coordinates voice transcription and complaint extraction without touching scores."""

    def __init__(self, client: OpenRouterClientProtocol) -> None:
        self._client = client

    async def transcribe_speech(
        self,
        audio: ValidatedAudioInput,
        language: str | None = None,
    ) -> TranscriptionResult:
        """2. Speech transcription via OpenRouter's dedicated `/audio/transcriptions` endpoint."""
        return await self._client.transcribe_audio(audio=audio, language=language)

    async def classify_complaint(
        self,
        transcript: ValidatedTranscript,
    ) -> StructuredComplaintAnalysis:
        """4. Complaint classification via OpenRouter `/chat/completions`."""
        if not transcript.is_usable:
            raise ValueError(
                f"Cannot classify unusable transcript (reason={transcript.rejection_reason})."
            )
        return await self._client.analyze_complaint(transcript.normalized_text)

    async def process_submission(
        self,
        *,
        facility_id: str,
        is_clean_vote: bool | None = None,
        audio_bytes: bytes | None = None,
        filename: str | None = None,
        content_type: str | None = None,
        explicit_format: str | None = None,
        language: str | None = None,
    ) -> VoiceFeedbackPipelineResult:
        """Execute the voice pipeline while keeping the YES/NO vote strictly independent."""
        cleanliness_vote_recorded = is_clean_vote is not None

        if audio_bytes is None:
            return VoiceFeedbackPipelineResult(
                facility_id=facility_id,
                cleanliness_vote_recorded=cleanliness_vote_recorded,
                is_clean_vote=is_clean_vote,
                citizen_vote_count=1,
                advisory_only=True,
                official_score_modified=False,
                maintenance_status_modified=False,
            )

        try:
            validated_audio = validate_audio_upload(
                audio_bytes,
                filename=filename,
                content_type=content_type,
                explicit_format=explicit_format,
            )
            transcription = await self.transcribe_speech(
                validated_audio, language=language
            )
            validated_tx = validate_transcript(transcription.text)
            if not validated_tx.is_usable:
                return VoiceFeedbackPipelineResult(
                    facility_id=facility_id,
                    cleanliness_vote_recorded=cleanliness_vote_recorded,
                    is_clean_vote=is_clean_vote,
                    citizen_vote_count=1,
                    advisory_only=True,
                    official_score_modified=False,
                    maintenance_status_modified=False,
                    transcript=validated_tx,
                    analysis=None,
                    voice_error=f"Transcript rejected: {validated_tx.rejection_reason}",
                )

            analysis = await self.classify_complaint(validated_tx)
            # Ensure primary category is always included in deduplicated extracted_categories
            merged_categories = extract_issue_categories(analysis)
            normalized_analysis = analysis.model_copy(
                update={"extracted_categories": merged_categories}
            )
            return VoiceFeedbackPipelineResult(
                facility_id=facility_id,
                cleanliness_vote_recorded=cleanliness_vote_recorded,
                is_clean_vote=is_clean_vote,
                citizen_vote_count=1,
                advisory_only=True,
                official_score_modified=False,
                maintenance_status_modified=False,
                transcript=validated_tx,
                analysis=normalized_analysis,
                voice_error=None,
            )
        except (AudioValidationError, OpenRouterError, ValueError) as exc:
            # Voice failure NEVER invalidates or drops the citizen's YES/NO vote
            return VoiceFeedbackPipelineResult(
                facility_id=facility_id,
                cleanliness_vote_recorded=cleanliness_vote_recorded,
                is_clean_vote=is_clean_vote,
                citizen_vote_count=1,
                advisory_only=True,
                official_score_modified=False,
                maintenance_status_modified=False,
                transcript=None,
                analysis=None,
                voice_error=str(exc),
            )
