"""Enumerations for the Government Monitoring module.

OWNER: Ibrahim
"""

from enum import StrEnum


class IssueType(StrEnum):
    cleaning = "cleaning"
    maintenance = "maintenance"


class IssueStatus(StrEnum):
    open = "open"
    alert_sent = "alert_sent"
    acknowledged = "acknowledged"
    escalated = "escalated"
    resolved = "resolved"
    dismissed = "dismissed"


class TriageLevel(StrEnum):
    """Government triage classification for ordering follow-up work.

    Not a cleanliness score, not a facility score, and not a substitute for the
    intelligence module's official scoring.
    """

    urgent = "urgent"
    high = "high"
    normal = "normal"
    unranked = "unranked"


class VerificationStatus(StrEnum):
    verified = "verified"
    unverified = "unverified"
    pending = "pending"


class FeedbackSource(StrEnum):
    """Strictly separate sources — never merged in any aggregate."""

    citizen_feedback = "citizen_feedback"
    evaluator_inspection = "evaluator_inspection"


class FeedbackSentiment(StrEnum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class FeedbackCategory(StrEnum):
    cleanliness_hygiene = "cleanliness_hygiene"
    water_availability = "water_availability"
    payment_experience = "payment_experience"
    broken_equipment = "broken_equipment"
    locked_facility = "locked_facility"
    lighting = "lighting"
    accessibility = "accessibility"
    safety = "safety"
    overall_satisfaction = "overall_satisfaction"
    other = "other"


class FeedbackChannel(StrEnum):
    app = "app"
    qr = "qr"
    web = "web"
    iot = "iot"  # Reserved for future physical button integration; not implemented in Phase 2


class CleanlinessVerdict(StrEnum):
    clean = "clean"
    needs_cleaning = "needs_cleaning"
    insufficient_data = "insufficient_data"


class NotificationChannel(StrEnum):
    email = "email"
    sms = "sms"  # Reserved enum value only; not implemented in Phase 2


class NotificationStatus(StrEnum):
    created = "created"
    sent = "sent"
    failed = "failed"
    acknowledged = "acknowledged"


class ConditionBand(StrEnum):
    recommended = "recommended"
    moderate = "moderate"
    attention = "attention"
    unscored = "unscored"

