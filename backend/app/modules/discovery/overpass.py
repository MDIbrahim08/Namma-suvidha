"""OpenStreetMap Overpass API client and query builder.

OWNER: Ibrahim

Uses `https://overpass-api.de/api/interpreter` with no paid API or API key.
"""

import asyncio
import logging
from typing import Any, Protocol

import httpx

logger = logging.getLogger("namma_suvidha.discovery.overpass")

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_OVERPASS_TIMEOUT_SECONDS = 25.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 1


class DiscoveryProviderError(Exception):
    """Base error raised when OpenStreetMap Overpass fails or returns invalid data."""

    def __init__(self, status_code: int, detail: str, code: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


class OverpassTimeoutError(DiscoveryProviderError):
    def __init__(
        self,
        detail: str = "OpenStreetMap Overpass request timed out. Please try again.",
    ) -> None:
        super().__init__(status_code=504, detail=detail, code="overpass_timeout")


class OverpassRateLimitError(DiscoveryProviderError):
    def __init__(
        self,
        detail: str = (
            "OpenStreetMap Overpass rate limit reached (HTTP 429). "
            "Please wait a moment and retry."
        ),
    ) -> None:
        super().__init__(status_code=429, detail=detail, code="overpass_rate_limited")


class OverpassUnavailableError(DiscoveryProviderError):
    def __init__(
        self,
        detail: str = "OpenStreetMap Overpass service is temporarily unavailable.",
    ) -> None:
        super().__init__(status_code=502, detail=detail, code="overpass_unavailable")


class OverpassResponseError(DiscoveryProviderError):
    def __init__(
        self,
        detail: str = "Received an invalid or malformed response from OpenStreetMap Overpass.",
    ) -> None:
        super().__init__(
            status_code=502, detail=detail, code="overpass_invalid_response"
        )


def build_overpass_toilet_query(
    latitude: float,
    longitude: float,
    radius_meters: int = 10000,
    timeout_seconds: int = 25,
) -> str:
    """Build the dynamic Overpass QL query for `amenity=toilets` within `radius_meters`."""
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError("latitude must be between -90 and 90")
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError("longitude must be between -180 and 180")
    if not (0 < radius_meters <= 10000):
        raise ValueError("radius must be between 1 and 10000 metres")

    lat_str = f"{latitude:.6f}"
    lon_str = f"{longitude:.6f}"
    return (
        f"[out:json][timeout:{int(timeout_seconds)}];\n"
        "(\n"
        f'  node["amenity"="toilets"](around:{int(radius_meters)},{lat_str},{lon_str});\n'
        f'  way["amenity"="toilets"](around:{int(radius_meters)},{lat_str},{lon_str});\n'
        f'  relation["amenity"="toilets"](around:{int(radius_meters)},{lat_str},{lon_str});\n'
        ");\n"
        "out center tags;"
    )


class OverpassClientProtocol(Protocol):
    async def fetch_toilets(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> list[dict[str, Any]]: ...


class OverpassHttpClient:
    """Asynchronous Overpass API client with bounded retry for transient failures."""

    def __init__(
        self,
        endpoint: str = DEFAULT_OVERPASS_URL,
        http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
        query_timeout_seconds: int = int(DEFAULT_OVERPASS_TIMEOUT_SECONDS),
        max_retries: int = MAX_RETRIES,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.http_timeout_seconds = http_timeout_seconds
        self.query_timeout_seconds = query_timeout_seconds
        self.max_retries = max(0, max_retries)
        self._transport = transport

    async def fetch_toilets(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> list[dict[str, Any]]:
        query = build_overpass_toilet_query(
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            timeout_seconds=self.query_timeout_seconds,
        )

        last_exc: DiscoveryProviderError | None = None
        attempts = self.max_retries + 1

        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.http_timeout_seconds),
                    transport=self._transport,
                    headers={
                        "User-Agent": "NammaSuvidha-Hackathon-MVP/0.1 (CS-26-0018)",
                        "Accept": "application/json",
                    },
                ) as client:
                    response = await client.post(
                        self.endpoint,
                        data={"data": query},
                    )
            except httpx.TimeoutException as exc:
                logger.warning(
                    "Overpass timeout on attempt %d/%d", attempt, attempts
                )
                last_exc = OverpassTimeoutError()
                if attempt < attempts:
                    await asyncio.sleep(0.25)
                    continue
                raise last_exc from exc
            except httpx.RequestError as exc:
                logger.warning(
                    "Overpass network error on attempt %d/%d: %s",
                    attempt,
                    attempts,
                    type(exc).__name__,
                )
                last_exc = OverpassUnavailableError(
                    "Unable to reach OpenStreetMap Overpass API due to a network error."
                )
                if attempt < attempts:
                    await asyncio.sleep(0.25)
                    continue
                raise last_exc from exc

            if response.status_code == 429:
                raise OverpassRateLimitError()

            if response.status_code == 504:
                last_exc = OverpassTimeoutError(
                    "OpenStreetMap Overpass server timed out (HTTP 504)."
                )
                if attempt < attempts:
                    await asyncio.sleep(0.25)
                    continue
                raise last_exc

            if response.status_code >= 500:
                last_exc = OverpassUnavailableError(
                    f"OpenStreetMap Overpass returned HTTP {response.status_code}."
                )
                if attempt < attempts:
                    await asyncio.sleep(0.25)
                    continue
                raise last_exc

            if response.status_code >= 400:
                raise OverpassResponseError(
                    f"OpenStreetMap Overpass rejected request with HTTP {response.status_code}."
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise OverpassResponseError(
                    "OpenStreetMap Overpass returned non-JSON content."
                ) from exc

            if not isinstance(payload, dict):
                raise OverpassResponseError(
                    "OpenStreetMap Overpass JSON root must be an object."
                )

            elements = payload.get("elements")
            if not isinstance(elements, list):
                raise OverpassResponseError(
                    "OpenStreetMap Overpass JSON response is missing an 'elements' list."
                )

            return [el for el in elements if isinstance(el, dict)]

        raise last_exc or OverpassUnavailableError()

