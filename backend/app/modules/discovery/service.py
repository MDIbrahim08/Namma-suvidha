"""Discovery service normalizing OpenStreetMap Overpass elements.

OWNER: Ibrahim
"""

from typing import Any

from app.modules.discovery.distance import haversine_distance_meters
from app.modules.discovery.overpass import OverpassClientProtocol
from app.modules.discovery.schemas import (
    AddressInformation,
    NearbyToilet,
    NearbyToiletResponse,
    OriginCoordinates,
)

VALID_OSM_TYPES = {"node", "way", "relation"}


def _extract_coordinates(element: dict[str, Any]) -> tuple[float, float] | None:
    """Extract `(latitude, longitude)` from an OSM node, way, or relation."""
    osm_type = element.get("type")
    lat_raw: Any = None
    lon_raw: Any = None

    if osm_type == "node":
        lat_raw = element.get("lat")
        lon_raw = element.get("lon")
    elif osm_type in {"way", "relation"}:
        center = element.get("center")
        if isinstance(center, dict):
            lat_raw = center.get("lat")
            lon_raw = center.get("lon")
        if lat_raw is None or lon_raw is None:
            lat_raw = element.get("lat")
            lon_raw = element.get("lon")

    if lat_raw is None or lon_raw is None or isinstance(lat_raw, bool) or isinstance(lon_raw, bool):
        return None

    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
    except (TypeError, ValueError):
        return None

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None

    return lat, lon


def _extract_name(tags: dict[str, str]) -> str | None:
    """Return available OSM name without inventing or fabricating a fallback string."""
    for key in ("name", "name:en", "official_name"):
        raw = tags.get(key)
        if raw and raw.strip():
            return raw.strip()
    return None


def _extract_address(tags: dict[str, str]) -> AddressInformation:
    """Extract available address tags, preserving `None` (`null`) when missing."""
    street_parts: list[str] = []
    housenumber = (tags.get("addr:housenumber") or "").strip()
    street = (tags.get("addr:street") or tags.get("addr:place") or "").strip()
    if housenumber and street:
        street_parts.append(f"{housenumber} {street}")
    elif street:
        street_parts.append(street)
    elif (tags.get("addr:full") or "").strip():
        street_parts.append(tags["addr:full"].strip())

    city = (
        tags.get("addr:city")
        or tags.get("addr:suburb")
        or tags.get("addr:district")
        or None
    )
    if city is not None:
        city = city.strip() or None

    postcode = tags.get("addr:postcode")
    if postcode is not None:
        postcode = postcode.strip() or None

    return AddressInformation(
        street=street_parts[0] if street_parts else None,
        city=city,
        postcode=postcode,
    )


def _normalise_tags(raw_tags: Any) -> dict[str, str]:
    if not isinstance(raw_tags, dict):
        return {}
    normalised: dict[str, str] = {}
    for key, val in raw_tags.items():
        if key is None or val is None:
            continue
        k = str(key).strip()
        v = str(val).strip()
        if k:
            normalised[k] = v
    return normalised


class ToiletDiscoveryService:
    """Fetches, normalizes, deduplicates, and sorts nearby OpenStreetMap toilets."""

    def __init__(self, overpass_client: OverpassClientProtocol) -> None:
        self._overpass = overpass_client

    async def find_nearby_toilets(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 10000,
    ) -> NearbyToiletResponse:
        raw_elements = await self._overpass.fetch_toilets(
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
        )

        seen_keys: set[tuple[str, int]] = set()
        results: list[tuple[float, NearbyToilet]] = []

        for element in raw_elements:
            osm_type = element.get("type")
            osm_id_raw = element.get("id")
            if (
                osm_type not in VALID_OSM_TYPES
                or osm_id_raw is None
                or isinstance(osm_id_raw, bool)
            ):
                continue

            try:
                osm_id = int(osm_id_raw)
            except (TypeError, ValueError):
                continue

            dedup_key = ( str(osm_type), osm_id )
            if dedup_key in seen_keys:
                continue

            coords = _extract_coordinates(element)
            if coords is None:
                continue

            seen_keys.add(dedup_key)
            el_lat, el_lon = coords
            tags = _normalise_tags(element.get("tags"))

            exact_distance_m = haversine_distance_meters(
                latitude, longitude, el_lat, el_lon
            )
            distance_meters = int(round(exact_distance_m))
            distance_km = round(exact_distance_m / 1000.0, 2)

            bbmp_facs = element.get("bbmp_facilities") or {}
            source_type = "BBMP" if element.get("bbmp_id") else "OpenStreetMap"

            toilet = NearbyToilet(
                osm_id=osm_id,
                osm_type=osm_type,  # type: ignore[arg-type]
                name=_extract_name(tags),
                latitude=el_lat,
                longitude=el_lon,
                distance_meters=distance_meters,
                distance_km=distance_km,
                address=_extract_address(tags),
                tags=tags,
                source=source_type,
                ward=element.get("bbmp_ward"),
                zone=element.get("bbmp_zone"),
                gents=bbmp_facs.get("gents"),
                ladies=bbmp_facs.get("ladies"),
                electricity=bbmp_facs.get("electricity"),
                water=bbmp_facs.get("water"),
                ugd=bbmp_facs.get("ugd"),
                year_of_construction=bbmp_facs.get("year"),
            )
            results.append((exact_distance_m, toilet))

        results.sort(key=lambda item: (item[0], item[1].osm_type, item[1].osm_id))
        sorted_toilets = [item[1] for item in results]

        overall_source = "OpenStreetMap"
        if sorted_toilets:
            if all(t.source == "BBMP" for t in sorted_toilets):
                overall_source = "BBMP"
            elif any(t.source == "BBMP" for t in sorted_toilets):
                overall_source = "BBMP+OSM"

        return NearbyToiletResponse(
            success=True,
            origin=OriginCoordinates(latitude=latitude, longitude=longitude),
            radius_meters=radius_meters,
            total_results=len(sorted_toilets),
            source=overall_source,
            results=sorted_toilets,
        )

