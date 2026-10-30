"""Application settings loaded from environment variables / backend/.env."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Namma Suvidha API"
    APP_ENV: Literal["development", "production"] = "development"
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    DATABASE_URL: str = ""

    # Placeholders only in Phase 0 - see docs/ENVIRONMENT.md.
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    GEMINI_API_KEY: str = ""

    # OpenRouter AI & Voice Feedback Pipeline configuration
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_API_KEY_VL: str = ""
    OPENROUTER_API_KEY_ULTRA: str = ""
    OPENROUTER_API_KEY_LIGHTNING: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    AUDIO_TRANSCRIPTION_MODEL: str = "deepgram/nova-3"
    COMPLAINT_ANALYSIS_MODEL: str = "google/gemini-3.8-flash"
    OPENROUTER_MULTIMODAL_MODEL: str = "nvidia/nemotron-3.5-super-vl:free"
    OPENROUTER_REASONING_MODEL: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    OPENROUTER_FAST_EXTRACTION_MODEL: str = "nvidia/nemotron-3.5-lightning:free"
    OPENROUTER_TIMEOUT_SECONDS: float = 30.0
    OPENROUTER_MAX_RETRIES: int = 2
    OPENROUTER_RETRY_BACKOFF_SECONDS: float = 0.5
    OPENROUTER_ALLOW_FREE_MODEL_SENSITIVE_DATA: bool = False
    VOICE_MAX_AUDIO_BYTES: int = 10 * 1024 * 1024
    IMAGE_MAX_BYTES: int = 10 * 1024 * 1024

    # Groq Speech-to-Text configuration
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_STT_PRIMARY_MODEL: str = "whisper-large-v3-turbo"
    GROQ_STT_FALLBACK_MODEL: str = "whisper-large-v3"
    GROQ_TIMEOUT_SECONDS: float = 30.0
    GROQ_MAX_RETRIES: int = 2
    GROQ_RETRY_BACKOFF_SECONDS: float = 0.5

    # Production AI provider routing (preserved defaults until benchmark review)
    AI_STT_PROVIDER: Literal["openrouter", "groq"] = "openrouter"
    AI_COMPLAINT_MODEL_TIER: Literal["legacy", "fast_extraction", "reasoning"] = "legacy"
    AI_EMAIL_DRAFT_MODEL_TIER: Literal["reasoning", "fast_extraction", "legacy"] = "reasoning"

    LOG_LEVEL: str = "INFO"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("postgres://"):
                return "postgresql+psycopg://" + stripped[len("postgres://") :]
            if stripped.startswith("postgresql://"):
                return "postgresql+psycopg://" + stripped[len("postgresql://") :]
            return stripped
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

