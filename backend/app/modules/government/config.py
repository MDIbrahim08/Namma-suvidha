"""Government module settings and Evaluator policy reference settings.

OWNER: Ibrahim
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class GovernmentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GOV_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    REPOSITORY_BACKEND: Literal["memory", "sql"] = "memory"
    ALLOWED_ROLES: Annotated[list[str], NoDecode] = ["government", "admin"]
    DEV_AUTH_BYPASS: bool = False
    DEV_FIXTURES_ENABLED: bool = False

    MAX_PAGE_SIZE: int = 100

    # Condition bands consuming official intelligence score
    SCORE_RECOMMENDED_MIN: float = 70.0
    SCORE_ATTENTION_MAX: float = 40.0

    # Reporting thresholds (independent of Shubham's 45-day evaluator cooldown)
    INSPECTION_STALE_DAYS: int = 45
    RECENT_INSPECTION_DAYS: int = 7
    PENDING_FEEDBACK_WINDOW_DAYS: int = 30

    # Repeated-complaint cluster thresholds
    REPEAT_WINDOW_DAYS: int = 14
    REPEAT_MIN_COUNT: int = 3
    REPEAT_MIN_REPORTERS: int = 2

    # Feedback-driven cleaning thresholds
    CLEAN_WINDOW_MINUTES: int = 60
    CLEAN_MIN_RESPONSES: int = 3
    CLEAN_NEGATIVE_RATIO: float = 0.5
    CLEAN_ESCALATE_AFTER_WINDOWS: int = 1
    CLEAN_LOW_USAGE_HOURS: int = 24
    CLEAN_AUTO_NOTIFY: bool = True

    # Notification provider: test only in Phase 2
    EMAIL_PROVIDER: Literal["test", "smtp"] = "test"

    @field_validator("ALLOWED_ROLES", mode="before")
    @classmethod
    def _split_roles(cls, value: object) -> object:
        if isinstance(value, str):
            return [r.strip().lower() for r in value.split(",") if r.strip()]
        return value


class EvaluatorPolicySettings(BaseSettings):
    """Configuration-only policy reference for physical verification requests.

    OWNER: Ibrahim (config holder) / Shubham (allocation & cooldown owner).
    No endpoints or allocation logic exist in Government; Evaluator + intelligence
    consume verification requests.
    """

    model_config = SettingsConfigDict(
        env_prefix="EVAL_POLICY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    max_daily_inspections_per_evaluator: int | None = None
    risk_based_reinspection_enabled: bool | None = None
    cooldown_days_reference: str = Field(
        default="45-day evaluator-toilet cooldown is owned by Shubham in app.modules.intelligence",
        frozen=True,
    )


def validate_government_startup(app_env: str, gov_settings: GovernmentSettings) -> None:
    """Refuse startup if dev bypass is enabled outside development or smtp is selected."""
    if gov_settings.DEV_AUTH_BYPASS and app_env != "development":
        raise RuntimeError(
            "GOV_DEV_AUTH_BYPASS=true is forbidden when APP_ENV != 'development'. "
            "Disable GOV_DEV_AUTH_BYPASS before starting in production."
        )
    if gov_settings.EMAIL_PROVIDER == "smtp":
        raise RuntimeError(
            "GOV_EMAIL_PROVIDER=smtp is not configured in Phase 2; use 'test'."
        )


@lru_cache
def get_government_settings() -> GovernmentSettings:
    return GovernmentSettings()


@lru_cache
def get_evaluator_policy_settings() -> EvaluatorPolicySettings:
    return EvaluatorPolicySettings()

