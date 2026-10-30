"""Pydantic v2 schemas for OpenStreetMap public toilet discovery.

OWNER: Ibrahim
"""

from typing import Literal

from pydantic import BaseModel, Field


class OriginCoordinates(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class AddressInformation(BaseModel):
    street: str | None = None
    city: str | None = None
    postcode: str | None = None


class NearbyToilet(BaseModel):
    osm_id: int
    osm_type: Literal["node", "way", "relation"]
    name: str | None = None
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    distance_meters: int = Field(..., ge=0)
    distance_km: float = Field(..., ge=0.0)
    address: AddressInformation
    tags: dict[str, str] = Field(default_factory=dict)
    source: Literal["OpenStreetMap", "BBMP"] = "OpenStreetMap"
    ward: str | None = None
    zone: str | None = None
    gents: bool | None = None
    ladies: bool | None = None
    electricity: bool | None = None
    water: bool | None = None
    ugd: bool | None = None
    year_of_construction: int | None = None


class NearbyToiletResponse(BaseModel):
    success: bool = True
    origin: OriginCoordinates
    radius_meters: int = Field(..., gt=0, le=10000)
    total_results: int = Field(..., ge=0)
    source: Literal["OpenStreetMap", "BBMP", "BBMP+OSM"] = "OpenStreetMap"
    results: list[NearbyToilet] = Field(default_factory=list)

