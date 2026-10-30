"""Groq Speech-to-Text HTTP client with primary (`whisper-large-v3-turbo`) and
accuracy fallback (`whisper-large-v3`) routing, timeouts, and exponential backoff.

OWNER: Ibrahim
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings
from app.modules.openrouter.schemas import (
    MIME_TYPE_TO_AUDIO_FORMAT,
    TranscriptionResult,
    TranscriptionUsage,
    ValidatedAudioInput,
)

logger = logging.getLogger("namma_suvidha.groq")

AUDIO_FORMAT_TO_MIME: dict[str, str] = {
    v: k for k, v in MIME_TYPE_TO_AUDIO_FORMAT.items()
}


class GroqError(Exception):
    """Base exception for Groq Speech-to-Text configuration, network, or provider errors."""

    def __init__(self, status_code: int, detail: str, code: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


class GroqConfigError(GroqError):
    def __init__(
        self,
        detail: str = "GROQ_API_KEY is not configured in the backend environment.",
    ) -> None:
        super().__init__(status_code=503, detail=detail, code="groq_not_configured")


class GroqTimeoutError(GroqError):
    def __init__(
        self,
        detail: str = "Groq Speech-to-Text request timed out.",
    ) -> None:
        super().__init__(status_code=504, detail=detail, code="groq_timeout")


class GroqProviderError(GroqError):
    def __init__(
        self,
        detail: str = "Groq provider returned an upstream error.",
        status_code: int = 502,
        code: str = "groq_provider_error",
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, code=code)


class GroqResponseValidationError(GroqError):
    def __init__(
        self,
        detail: str = "Groq returned a malformed or unparseable JSON response.",
    ) -> None:
        super().__init__(status_code=502, detail=detail, code="groq_invalid_response")


class GroqClientProtocol(Protocol):
    async def transcribe_audio(
        self,
        audio: ValidatedAudioInput,
        language: str | None = None,
        *,
        use_fallback_model: bool = False,
        model_override: str | None = None,
    ) -> TranscriptionResult: ...

    async def transcribe_with_accuracy_fallback(
        self,
        audio: ValidatedAudioInput,
        language: str | None = None,
        *,
        min_chars: int = 2,
    ) -> TranscriptionResult: ...


class GroqHttpClient:
    """Async Groq Speech-to-Text client supporting `whisper-large-v3-turbo` and
    fallback `whisper-large-v3` via `POST /audio/transcriptions` (multipart/form-data).
    """

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport

    @property
    def base_url(self) -> str:
        url = (self._settings.GROQ_BASE_URL or "").strip().rstrip("/")
        if not url:
            raise GroqConfigError("GROQ_BASE_URL must not be empty.")
        return url

    @property
    def api_key(self) -> str:
        key = (self._settings.GROQ_API_KEY or "").strip()
        if not key:
            raise GroqConfigError(
                "GROQ_API_KEY is missing. Set it in backend/.env before calling Groq."
            )
        return key

    @property
    def primary_model(self) -> str:
        model = (self._settings.GROQ_STT_PRIMARY_MODEL or "").strip()
        if not model:
            raise GroqConfigError("GROQ_STT_PRIMARY_MODEL must not be empty.")
        return model

    @property
    def fallback_model(self) -> str:
        model = (self._settings.GROQ_STT_FALLBACK_MODEL or "").strip()
        if not model:
            raise GroqConfigError("GROQ_STT_FALLBACK_MODEL must not be empty.")
        return model

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    async def _post_multipart(
        self,
        path: str,
        *,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str],
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        max_retries = max(0, int(getattr(self._settings, "GROQ_MAX_RETRIES", 0)))
        backoff_base = float(
            getattr(self._settings, "GROQ_RETRY_BACKOFF_SECONDS", 0.5)
        )
        headers = self._headers()

        response: httpx.Response | None = None
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self._settings.GROQ_TIMEOUT_SECONDS),
                    transport=self._transport,
                    headers=headers,
                ) as client:
                    response = await client.post(url, files=files, data=data)
            except httpx.TimeoutException as exc:
                if attempt < max_retries and self._transport is None:
                    await asyncio.sleep(backoff_base * (2**attempt))
                    continue
                logger.warning("Groq request timed out for %s", path)
                raise GroqTimeoutError(
                    f"Groq request to {path} timed out after "
                    f"{self._settings.GROQ_TIMEOUT_SECONDS}s."
                ) from exc
            except httpx.RequestError as exc:
                if attempt < max_retries and self._transport is None:
                    await asyncio.sleep(backoff_base * (2**attempt))
                    continue
                logger.warning(
                    "Groq network error for %s: %s", path, type(exc).__name__
                )
                raise GroqProviderError(
                    f"Network error communicating with Groq ({type(exc).__name__})."
                ) from exc

            if response.status_code in (429, 502, 503, 504) and (
                attempt < max_retries and self._transport is None
            ):
                await asyncio.sleep(backoff_base * (2**attempt))
                continue
            break

        assert response is not None
        if response.status_code == 429:
            raise GroqProviderError(
                detail="Groq rate limit exceeded (HTTP 429).",
                status_code=429,
                code="groq_rate_limited",
            )

        if response.status_code >= 500:
            raise GroqProviderError(
                detail=f"Groq upstream server error (HTTP {response.status_code}).",
                status_code=502,
                code="groq_upstream_error",
            )

        if response.status_code >= 400:
            detail_msg = f"Groq rejected request with HTTP {response.status_code}."
            try:
                err_body = response.json()
                if isinstance(err_body, dict) and isinstance(
                    err_body.get("error"), dict
                ):
                    upstream_msg = err_body["error"].get("message")
                    if upstream_msg:
                        detail_msg = f"{detail_msg} ({upstream_msg})"
            except ValueError:
                pass
            raise GroqProviderError(
                detail=detail_msg,
                status_code=502,
                code="groq_request_rejected",
            )

        try:
            parsed = response.json()
        except ValueError as exc:
            raise GroqResponseValidationError("Groq returned non-JSON body.") from exc

        if not isinstance(parsed, dict):
            raise GroqResponseValidationError(
                "Groq response root must be a JSON object."
            )
        return parsed

    async def transcribe_audio(
        self,
        audio: ValidatedAudioInput,
        language: str | None = None,
        *,
        use_fallback_model: bool = False,
        model_override: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio using Groq's `POST /audio/transcriptions` endpoint."""
        if model_override:
            model_id = model_override.strip()
        else:
            model_id = (
                self.fallback_model if use_fallback_model else self.primary_model
            )

        raw_bytes = base64.b64decode(audio.base64_data)
        mime_type = AUDIO_FORMAT_TO_MIME.get(
            audio.audio_format, f"audio/{audio.audio_format}"
        )
        filename = f"audio.{audio.audio_format}"

        form_data: dict[str, str] = {
            "model": model_id,
            "temperature": "0",
            "response_format": "verbose_json",
        }
        if language:
            form_data["language"] = language

        files = {"file": (filename, raw_bytes, mime_type)}
        resp_json = await self._post_multipart(
            "/audio/transcriptions", files=files, data=form_data
        )

        text = resp_json.get("text")
        if not isinstance(text, str):
            raise GroqResponseValidationError(
                "Groq transcription response is missing string field 'text'."
            )

        duration = resp_json.get("duration")
        duration_seconds = (
            float(duration) if isinstance(duration, int | float) else None
        )
        detected_lang = resp_json.get("language")
        resolved_lang = (
            detected_lang if isinstance(detected_lang, str) else language
        )

        usage_obj: TranscriptionUsage | None = None
        if isinstance(resp_json.get("usage"), dict):
            usage_obj = TranscriptionUsage.model_validate(resp_json["usage"])
        elif duration_seconds is not None:
            usage_obj = TranscriptionUsage(seconds=duration_seconds)

        return TranscriptionResult(
            text=text,
            model=model_id,
            language=resolved_lang,
            duration_seconds=duration_seconds,
            usage=usage_obj,
        )

    async def transcribe_with_accuracy_fallback(
        self,
        audio: ValidatedAudioInput,
        language: str | None = None,
        *,
        min_chars: int = 2,
    ) -> TranscriptionResult:
        """Attempt transcription with `GROQ_STT_PRIMARY_MODEL` (`whisper-large-v3-turbo`);
        automatically fall back to `GROQ_STT_FALLBACK_MODEL` (`whisper-large-v3`) if the
        primary model raises a provider/timeout error or returns an empty/too-short transcript.
        """
        try:
            primary_res = await self.transcribe_audio(
                audio, language=language, use_fallback_model=False
            )
            if len(primary_res.text.strip()) >= min_chars:
                return primary_res
            logger.info(
                "Groq primary model %s returned short/empty transcript; "
                "retrying with fallback model %s",
                self.primary_model,
                self.fallback_model,
            )
        except (GroqProviderError, GroqTimeoutError) as exc:
            logger.warning(
                "Groq primary model %s failed (%s); falling back to %s",
                self.primary_model,
                exc.code,
                self.fallback_model,
            )

        return await self.transcribe_audio(
            audio, language=language, use_fallback_model=True
        )

