"""BBMP static data client adhering to OverpassClientProtocol.

OWNER: Ibrahim
"""

from __future__ import annotations

from typing import Any

from app.modules.discovery.bbmp_loader import load_bbmp_records
from app.modules.discovery.distance import haversine_distance_meters
from app.modules.discovery.overpass import OverpassClientProtocol


class BBMPStaticClient:
    """Delivers real BBMP Bengaluru municipal toilet records adhering to OverpassClientProtocol."""

    def __init__(self) -> None:
        self._records = load_bbmp_records()

    async def fetch_toilets(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> list[dict[str, Any]]:
        elements: list[dict[str, Any]] = []

        for idx, rec in enumerate(self._records, start=100000):
            dist = haversine_distance_meters(latitude, longitude, rec.latitude, rec.longitude)
            if dist <= radius_meters:
                tags: dict[str, str] = {
                    "amenity": "toilets",
                    "name": rec.display_name,
                    "operator": "BBMP",
                    "source": "BBMP Open Data",
                }
                if rec.road_street:
                    tags["addr:street"] = rec.road_street
                if rec.ward_name:
                    tags["addr:suburb"] = rec.ward_name
                if rec.zone:
                    tags["addr:district"] = rec.zone
                if rec.has_gents is not None:
                    tags["male"] = "yes" if rec.has_gents else "no"
                if rec.has_ladies is not None:
                    tags["female"] = "yes" if rec.has_ladies else "no"
                if rec.has_water is not None:
                    tags["drinking_water"] = "yes" if rec.has_water else "no"
                if rec.has_electricity is not None:
                    tags["lit"] = "yes" if rec.has_electricity else "no"
                if rec.contractor_name:
                    tags["contractor"] = rec.contractor_name

                elements.append(
                    {
                        "type": "node",
                        "id": idx,
                        "lat": rec.latitude,
                        "lon": rec.longitude,
                        "tags": tags,
                        "bbmp_id": rec.id,
                        "bbmp_ward": rec.ward_name or rec.ward_no,
                        "bbmp_zone": rec.zone,
                        "bbmp_facilities": {
                            "gents": rec.has_gents,
                            "ladies": rec.has_ladies,
                            "electricity": rec.has_electricity,
                            "water": rec.has_water,
                            "ugd": rec.has_ugd,
                            "water_tank": rec.has_water_tank,
                            "bwssb": rec.has_bwssb,
                            "bore_well": rec.has_bore_well,
                            "year": rec.year_of_construction,
                        },
                    }
                )

        return elements

