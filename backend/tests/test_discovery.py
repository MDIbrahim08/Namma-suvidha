"""Unit and integration tests for OpenStreetMap toilet discovery (`/api/toilets/nearby`).

Covers items 7-26 of Phase 10 testing requirements using mocked Overpass responses.
"""

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.discovery.distance import haversine_distance_meters
from app.modules.discovery.overpass import (
    OverpassClientProtocol,
    OverpassHttpClient,
    build_overpass_toilet_query,
)
from app.modules.discovery.router import get_overpass_client


class FakeOverpassClient(OverpassClientProtocol):
    def __init__(self, elements: list[dict[str, Any]]) -> None:
        self.elements = elements
        self.calls: list[tuple[float, float, int]] = []

    async def fetch_toilets(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> list[dict[str, Any]]:
        self.calls.append((latitude, longitude, radius_meters))
        return self.elements


def test_dynamic_overpass_query_generation() -> None:
    """Item 12: Dynamic Overpass query generation uses exact latitude, longitude, and radius."""
    query = build_overpass_toilet_query(13.0827, 80.2707, radius_meters=7500)
    assert "[out:json][timeout:25];" in query
    assert 'node["amenity"="toilets"](around:7500,13.082700,80.270700);' in query
    assert 'way["amenity"="toilets"](around:7500,13.082700,80.270700);' in query
    assert 'relation["amenity"="toilets"](around:7500,13.082700,80.270700);' in query
    assert "out center tags;" in query


@pytest.mark.parametrize(
    ("lat", "lon", "radius"),
    [
        (-95.0, 77.0, 1000),  # Item 8: Invalid latitude (< -90)
        (91.5, 77.0, 1000),  # Item 8: Invalid latitude (> 90)
        (12.9, -181.0, 1000),  # Item 9: Invalid longitude (< -180)
        (12.9, 185.0, 1000),  # Item 9: Invalid longitude (> 180)
        (12.9, 77.0, 0),  # Item 11: Radius <= 0
        (12.9, 77.0, -500),  # Item 11: Negative radius
        (12.9, 77.0, 10001),  # Item 11: Exceeds maximum radius 10000
    ],
)
def test_coordinate_and_radius_validation_rejects_invalid_inputs(
    lat: float, lon: float, radius: int
) -> None:
    """Items 8, 9, 11: Invalid coordinates or radius values return HTTP 422."""
    app = create_app()
    fake = FakeOverpassClient([])
    app.dependency_overrides[get_overpass_client] = lambda: fake

    with TestClient(app) as client:
        res = client.get(
            "/api/toilets/nearby",
            params={"latitude": lat, "longitude": lon, "radius": radius},
        )
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"
    assert len(fake.calls) == 0


def test_default_radius_is_10000_meters_and_both_routes_resolve() -> None:
    """Items 7, 10, 22: Valid coordinates use default radius 10000 and handle empty results."""
    app = create_app()
    fake = FakeOverpassClient([])
    app.dependency_overrides[get_overpass_client] = lambda: fake

    with TestClient(app) as client:
        res_api = client.get(
            "/api/toilets/nearby",
            params={"latitude": 19.0760, "longitude": 72.8777},
        )
        res_v1 = client.get(
            "/api/v1/toilets/nearby",
            params={"latitude": 19.0760, "longitude": 72.8777},
        )

    for res in (res_api, res_v1):
        assert res.status_code == 200
        body = res.json()
        assert body == {
            "success": True,
            "origin": {"latitude": 19.076, "longitude": 72.8777},
            "radius_meters": 10000,
            "total_results": 0,
            "source": "OpenStreetMap",
            "results": [],
        }

    assert fake.calls == [
        (19.076, 72.8777, 10000),
        (19.076, 72.8777, 10000),
    ]


def test_node_way_relation_parsing_tags_distances_sorting_and_deduplication() -> None:
    """Items 13-21: Parse nodes, ways (center), relations (center), preserve tags,
    handle missing name/address as null, deduplicate, and sort by ascending distance.
    """
    origin_lat = 28.6139
    origin_lon = 77.2090

    raw_elements: list[dict[str, Any]] = [
        # Relation (further away, ~1.1 km north)
        {
            "type": "relation",
            "id": 3003,
            "center": {"lat": 28.6239, "lon": 77.2090},
            "tags": {
                "amenity": "toilets",
                "name": "Connaught Place Transit Block",
                "addr:street": "Parliament Street",
                "addr:city": "New Delhi",
                "addr:postcode": "110001",
                "wheelchair": "yes",
                "fee": "no",
            },
        },
        # Node (closest, ~111m north, missing name & address)
        {
            "type": "node",
            "id": 1001,
            "lat": 28.6149,
            "lon": 77.2090,
            "tags": {
                "amenity": "toilets",
                "access": "permissive",
                "unisex": "yes",
            },
        },
        # Duplicate of node 1001 (must be ignored)
        {
            "type": "node",
            "id": 1001,
            "lat": 28.6149,
            "lon": 77.2090,
            "tags": {"amenity": "toilets"},
        },
        # Way with center coordinates (~334m north)
        {
            "type": "way",
            "id": 2002,
            "center": {"lat": 28.6169, "lon": 77.2090},
            "tags": {
                "amenity": "toilets",
                "name:en": "Janpath Public Restroom",
                "addr:housenumber": "14",
                "addr:street": "Janpath Road",
                "changing_table": "yes",
            },
        },
        # Way missing center coordinates (must be skipped safely)
        {
            "type": "way",
            "id": 9999,
            "tags": {"amenity": "toilets", "name": "Broken Geometry"},
        },
    ]

    app = create_app()
    fake = FakeOverpassClient(raw_elements)
    app.dependency_overrides[get_overpass_client] = lambda: fake

    with TestClient(app) as client:
        res = client.get(
            "/api/toilets/nearby",
            params={"latitude": origin_lat, "longitude": origin_lon, "radius": 5000},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["origin"] == {"latitude": origin_lat, "longitude": origin_lon}
    assert body["radius_meters"] == 5000
    assert body["source"] == "OpenStreetMap"
    assert body["total_results"] == 3

    results = body["results"]
    # Sorted by ascending distance: node 1001 -> way 2002 -> relation 3003
    assert [r["osm_id"] for r in results] == [1001, 2002, 3003]
    assert [r["osm_type"] for r in results] == ["node", "way", "relation"]

    # Item 16 & 17: Missing name and address fields are null (None), never fabricated
    first = results[0]
    assert first["name"] is None
    assert first["address"] == {"street": None, "city": None, "postcode": None}
    assert first["tags"] == {
        "amenity": "toilets",
        "access": "permissive",
        "unisex": "yes",
    }
    expected_m = int(
        round(haversine_distance_meters(origin_lat, origin_lon, 28.6149, 77.2090))
    )
    assert first["distance_meters"] == expected_m
    assert first["distance_km"] == round(expected_m / 1000.0, 2)

    # Way center & partial address
    second = results[1]
    assert second["name"] == "Janpath Public Restroom"
    assert second["latitude"] == 28.6169
    assert second["longitude"] == 77.2090
    assert second["address"] == {
        "street": "14 Janpath Road",
        "city": None,
        "postcode": None,
    }
    assert second["tags"]["changing_table"] == "yes"

    # Relation center & full address
    third = results[2]
    assert third["name"] == "Connaught Place Transit Block"
    assert third["address"] == {
        "street": "Parliament Street",
        "city": "New Delhi",
        "postcode": "110001",
    }
    assert third["tags"]["wheelchair"] == "yes"
    assert third["tags"]["fee"] == "no"


def test_overpass_timeout_returns_504() -> None:
    """Item 23: Overpass timeout returns HTTP 504 with clear error code."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timed out reading from Overpass")

    client_instance = OverpassHttpClient(
        max_retries=0, transport=httpx.MockTransport(handler)
    )
    app = create_app()
    app.dependency_overrides[get_overpass_client] = lambda: client_instance

    with TestClient(app) as client:
        res = client.get(
            "/api/toilets/nearby", params={"latitude": 13.0, "longitude": 80.0}
        )

    assert res.status_code == 504
    assert res.json()["code"] == "overpass_timeout"


def test_overpass_http_429_rate_limit_returns_429() -> None:
    """Item 24: HTTP 429 from Overpass returns HTTP 429 rate limit error."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    client_instance = OverpassHttpClient(
        max_retries=0, transport=httpx.MockTransport(handler)
    )
    app = create_app()
    app.dependency_overrides[get_overpass_client] = lambda: client_instance

    with TestClient(app) as client:
        res = client.get(
            "/api/toilets/nearby", params={"latitude": 13.0, "longitude": 80.0}
        )

    assert res.status_code == 429
    assert res.json()["code"] == "overpass_rate_limited"


def test_overpass_http_5xx_returns_502_after_bounded_retry() -> None:
    """Item 25: HTTP 5xx from Overpass retries once and returns HTTP 502."""
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, text="Service Unavailable")

    client_instance = OverpassHttpClient(
        max_retries=1, transport=httpx.MockTransport(handler)
    )
    app = create_app()
    app.dependency_overrides[get_overpass_client] = lambda: client_instance

    with TestClient(app) as client:
        res = client.get(
            "/api/toilets/nearby", params={"latitude": 13.0, "longitude": 80.0}
        )

    assert res.status_code == 502
    assert res.json()["code"] == "overpass_unavailable"
    assert attempts == 2


@pytest.mark.parametrize(
    "bad_body",
    [
        "<html>Gateway Error</html>",  # Non-JSON
        '["not", "an", "object"]',  # JSON array instead of object
        '{"remark": "runtime error: missing elements"}',  # Missing 'elements' list
    ],
)
def test_overpass_malformed_response_returns_502(bad_body: str) -> None:
    """Item 26: Malformed or non-JSON Overpass payload returns HTTP 502."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=bad_body)

    client_instance = OverpassHttpClient(
        max_retries=0, transport=httpx.MockTransport(handler)
    )
    app = create_app()
    app.dependency_overrides[get_overpass_client] = lambda: client_instance

    with TestClient(app) as client:
        res = client.get(
            "/api/toilets/nearby", params={"latitude": 13.0, "longitude": 80.0}
        )

    assert res.status_code == 502
    assert res.json()["code"] == "overpass_invalid_response"

