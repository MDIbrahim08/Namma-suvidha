"""Pydantic v2 schemas and enums for OpenRouter AI & Voice Feedback Pipeline.

OWNER: Ibrahim

Important architectural invariants:
- The citizen's one-tap YES/NO cleanliness vote (`is_clean`) is strictly independent
  of voice transcription, moderation, and complaint classification.
- Multiple issue categories extracted from a single voice clip still represent
  at most one citizen feedback record / one vote (`vote_weight = 1`).
- AI model output is advisory metadata (`advisory_only = True`) and NEVER directly
  mutates Shubham's official facility scores or Government maintenance issue statuses.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_AUDIO_FORMATS: frozenset[str] = frozenset(
    {"wav", "mp3", "mp4", "m4a", "flac", "ogg", "oga", "webm"}
)

MIME_TYPE_TO_AUDIO_FORMAT: dict[str, str] = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "audio/ogg": "ogg",
    "audio/vorbis": "ogg",
    "audio/webm": "webm",
}


class VoiceIssueCategory(StrEnum):
    CLEANLINESS = "cleanliness"
    WATER = "water"
    ODOR = "odor"
    LIGHTING = "lighting"
    LOCKED = "locked"
    PLUMBING = "plumbing"
    SUPPLIES = "supplies"
    ACCESSIBILITY = "accessibility"
    SAFETY = "safety"
    OTHER = "other"


class ModerationClassification(StrEnum):
    CLEAN = "clean"
    SPAM = "spam"
    ABUSE = "abuse"
    GIBBERISH = "gibberish"


class ComplaintSentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ValidatedAudioInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    audio_format: Literal["wav", "mp3", "mp4", "m4a", "flac", "ogg", "oga", "webm"]
    size_bytes: int = Field(..., gt=0)
    base64_data: str = Field(..., min_length=4)


class TranscriptionUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_tokens: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    seconds: float | None = None
    cost: float | None = None


class TranscriptionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    model: str
    language: str | None = None
    duration_seconds: float | None = None
    usage: TranscriptionUsage | None = None


class ValidatedTranscript(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw_text: str
    normalized_text: str
    word_count: int = Field(..., ge=0)
    is_usable: bool
    rejection_reason: str | None = None


class StructuredComplaintAnalysis(BaseModel):
    """Structured JSON output validated from the complaint analysis LLM."""

    model_config = ConfigDict(extra="forbid")

    is_complaint: bool
    sentiment: ComplaintSentiment
    primary_category: VoiceIssueCategory
    extracted_categories: list[VoiceIssueCategory] = Field(default_factory=list)
    urgency_score: int = Field(..., ge=1, le=5)
    summary: str = Field(..., min_length=1, max_length=500)
    moderation_status: ModerationClassification = ModerationClassification.CLEAN
    moderation_reason: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @field_validator("extracted_categories", mode="after")
    @classmethod
    def _deduplicate_categories(
        cls, categories: list[VoiceIssueCategory]
    ) -> list[VoiceIssueCategory]:
        seen: list[VoiceIssueCategory] = []
        for cat in categories:
            if cat not in seen:
                seen.append(cat)
        return seen


class VoiceFeedbackPipelineResult(BaseModel):
    """Final non-destructive result of processing a citizen submission."""

    model_config = ConfigDict(frozen=True)

    facility_id: str
    # Original YES/NO cleanliness vote is preserved independently of voice processing
    cleanliness_vote_recorded: bool
    is_clean_vote: bool | None = None
    # Regardless of extracted category count, this submission counts as 1 citizen vote
    citizen_vote_count: Literal[1] = 1
    # Marks AI output as advisory so it never directly alters official scores or statuses
    advisory_only: Literal[True] = True
    official_score_modified: Literal[False] = False
    maintenance_status_modified: Literal[False] = False
    transcript: ValidatedTranscript | None = None
    analysis: StructuredComplaintAnalysis | None = None
    voice_error: str | None = None


SUPPORTED_IMAGE_MIME_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)


class DataSensitivityClassification(StrEnum):
    """Privacy classification enforced before calling free-tier OpenRouter models."""

    ANONYMIZED_TEST_DATA = "anonymized_test_data"
    PUBLIC_SANITATION_SYNTHETIC = "public_sanitation_synthetic"
    RAW_CITIZEN_VOICE = "raw_citizen_voice"
    GOVERNMENT_ID_DOCUMENT = "government_id_document"
    PERSONAL_IDENTITY_INFO = "personal_identity_info"
    PRIVATE_IDENTIFIABLE_INSPECTION_PHOTO = "private_identifiable_inspection_photo"


FORBIDDEN_FREE_ENDPOINT_CLASSIFICATIONS: frozenset[DataSensitivityClassification] = (
    frozenset(
        {
            DataSensitivityClassification.RAW_CITIZEN_VOICE,
            DataSensitivityClassification.GOVERNMENT_ID_DOCUMENT,
            DataSensitivityClassification.PERSONAL_IDENTITY_INFO,
            DataSensitivityClassification.PRIVATE_IDENTIFIABLE_INSPECTION_PHOTO,
        }
    )
)


class ValidatedImageInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(..., gt=0)
    base64_data: str = Field(..., min_length=4)
    data_uri: str = Field(..., min_length=15)
    sensitivity: DataSensitivityClassification = (
        DataSensitivityClassification.ANONYMIZED_TEST_DATA
    )


class InspectionImageDefect(StrEnum):
    FLOOR_SOILING = "floor_soiling"
    TOILET_BOWL_STAINING = "toilet_bowl_staining"
    STANDING_WATER = "standing_water"
    BROKEN_FIXTURE = "broken_fixture"
    MISSING_WATER_TAP = "missing_water_tap"
    POOR_LIGHTING = "poor_lighting"
    DOOR_LOCK_DAMAGE = "door_lock_damage"
    OVERFLOWING_BIN = "overflowing_bin"
    GRAFFITI_OR_VANDALISM = "graffiti_or_vandalism"
    NONE_OBSERVED = "none_observed"


class StructuredImageInspectionAnalysis(BaseModel):
    """Strict Pydantic schema for multimodal toilet inspection image analysis.

    Advisory only — never directly modifies facility scores, evaluator approvals,
    payment amounts, or facility availability states.
    """

    model_config = ConfigDict(extra="forbid")

    is_washroom_image: bool
    contains_identifiable_person_or_id: bool = False
    visual_cleanliness_band: Literal["clean", "moderate", "dirty", "unusable"]
    detected_defects: list[InspectionImageDefect] = Field(default_factory=list)
    water_fixture_visible: bool = False
    lighting_adequate: bool = True
    summary: str = Field(..., min_length=1, max_length=600)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    advisory_only: Literal[True] = True
    official_score_modified: Literal[False] = False
    evaluator_approval_modified: Literal[False] = False
    payment_amount_modified: Literal[False] = False
    availability_state_modified: Literal[False] = False

    @field_validator("detected_defects", mode="after")
    @classmethod
    def _deduplicate_defects(
        cls, defects: list[InspectionImageDefect]
    ) -> list[InspectionImageDefect]:
        seen: list[InspectionImageDefect] = []
        for item in defects:
            if item not in seen:
                seen.append(item)
        return seen


class StructuredMaintenanceEmailDraft(BaseModel):
    """Strict Pydantic schema for AI-assisted operator/ward maintenance alert email drafting.

    Advisory only — never directly triggers resolution, score mutation, or payouts.
    """

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(..., min_length=5, max_length=200)
    salutation: str = Field(..., min_length=2, max_length=120)
    executive_summary: str = Field(..., min_length=10, max_length=600)
    action_items: list[str] = Field(..., min_length=1, max_length=10)
    urgency_label: Literal["routine", "priority", "urgent", "critical"]
    closing: str = Field(..., min_length=2, max_length=200)
    advisory_only: Literal[True] = True
    official_score_modified: Literal[False] = False
    evaluator_approval_modified: Literal[False] = False
    payment_amount_modified: Literal[False] = False
    availability_state_modified: Literal[False] = False
