"""Configuration settings for the Evaluator Authentication & Management module.

OWNER: Ibrahim
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.modules.evaluator.exceptions import EvaluatorSchemaPendingError


class EvaluatorModuleSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EVAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    REPOSITORY_BACKEND: Literal["memory", "sql"] = "memory"

    # WebAuthn Relying Party configuration
    WEBAUTHN_RP_ID: str = "localhost"
    WEBAUTHN_RP_NAME: str = "Namma Suvidha Evaluator"
    WEBAUTHN_EXPECTED_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    WEBAUTHN_CHALLENGE_TTL_SECONDS: int = 300

    # Private ID storage & retention configuration
    ID_STORAGE_BUCKET: str = "evaluator-ids"
    EVIDENCE_STORAGE_BUCKET: str = "inspection-evidence"
    ID_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB
    ID_SIGNED_URL_TTL_SECONDS: int = 60  # Short-lived 60-second admin preview URL
    ID_RETENTION_DAYS_AFTER_DECISION: int = 7

    # Pagination
    MAX_PAGE_SIZE: int = 100

    @field_validator("WEBAUTHN_EXPECTED_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


def validate_evaluator_startup(
    app_env: str, eval_settings: EvaluatorModuleSettings
) -> None:
    """Enforce fail-closed repository rule in production:
    In-memory storage is for development and deterministic tests only.
    Production must fail closed if SQL persistence is not selected or unavailable.
    """
    if app_env != "development" and eval_settings.REPOSITORY_BACKEND == "memory":
        raise EvaluatorSchemaPendingError(
            "EVAL_REPOSITORY_BACKEND='memory' is forbidden when APP_ENV != 'development'. "
            "Production must use SQL persistence and fail closed if unavailable."
        )


@lru_cache
def get_evaluator_module_settings() -> EvaluatorModuleSettings:
    return EvaluatorModuleSettings()

