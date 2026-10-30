"""FastAPI router for OpenStreetMap public toilet discovery.

OWNER: Ibrahim
"""

import os
from fastapi import APIRouter, Depends, Query

from app.modules.discovery.bbmp_client import BBMPStaticClient
from app.modules.discovery.overpass import (
    OverpassClientProtocol,
    OverpassHttpClient,
)
from app.modules.discovery.schemas import NearbyToiletResponse
from app.modules.discovery.service import ToiletDiscoveryService

_DEFAULT_OVERPASS_CLIENT = OverpassHttpClient()
_DEFAULT_BBMP_CLIENT = BBMPStaticClient()


def get_overpass_client() -> OverpassClientProtocol:
    # Use real BBMP dataset by default unless USE_OVERPASS_API is explicitly set to true
    if os.getenv("USE_OVERPASS_API", "false").lower() in {"true", "1"}:
        return _DEFAULT_OVERPASS_CLIENT
    return _DEFAULT_BBMP_CLIENT


def get_discovery_service(
    overpass_client: OverpassClientProtocol = Depends(get_overpass_client),
) -> ToiletDiscoveryService:
    return ToiletDiscoveryService(overpass_client=overpass_client)


router = APIRouter(prefix="/toilets", tags=["citizen"])


@router.get("/nearby", response_model=NearbyToiletResponse)
async def get_nearby_toilets(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Device latitude in WGS84"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Device longitude in WGS84"),
    radius: int = Query(
        default=10000,
        gt=0,
        le=10000,
        description="Search radius in metres (default 10000, maximum 10000)",
    ),
    service: ToiletDiscoveryService = Depends(get_discovery_service),
) -> NearbyToiletResponse:
    """Discover nearby OpenStreetMap `amenity=toilets` records around `(latitude, longitude)`."""
    return await service.find_nearby_toilets(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius,
    )

