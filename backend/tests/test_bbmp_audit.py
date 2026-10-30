import pytest
from app.modules.discovery.bbmp_loader import (
    load_bbmp_records,
    _parse_bool,
    _clean_str,
    _parse_year,
)
from app.modules.discovery.bbmp_client import BBMPStaticClient
from app.modules.discovery.service import ToiletDiscoveryService
from app.modules.discovery.distance import haversine_distance_meters


def test_bbmp_loader_data_quality_and_stats():
    records = load_bbmp_records()
    assert len(records) == 479  # 480 rows in CSV, 1 has invalid/unparsable coords

    # Check bounds
    for r in records:
        assert 12.0 <= r.latitude <= 14.5
        assert 76.5 <= r.longitude <= 78.5
        assert r.id.startswith("bbmp-w")

    # Check sample parsing
    assert _parse_bool("Yes") is True
    assert _parse_bool("No") is False
    assert _parse_bool("-") is None
    assert _parse_bool("") is None
    assert _clean_str("-") is None
    assert _clean_str("  BBMP  ") == "BBMP"
    assert _parse_year("2013") == 2013
    assert _parse_year("2002-03") == 2002
    assert _parse_year("19830") is None  # Correctly filters out typo year


@pytest.mark.anyio
async def test_bbmp_client_radii_and_sorting():
    client = BBMPStaticClient()
    service = ToiletDiscoveryService(overpass_client=client)

    # Majestic coordinates
    lat, lon = 12.9767, 77.5713

    # Small radius (500m)
    res_500 = await service.find_nearby_toilets(latitude=lat, longitude=lon, radius_meters=500)
    assert res_500.success is True

    # Larger radius (3000m)
    res_3000 = await service.find_nearby_toilets(latitude=lat, longitude=lon, radius_meters=3000)
    assert res_3000.success is True
    assert res_3000.total_results >= res_500.total_results

    # Verify sorting by distance
    distances = [t.distance_meters for t in res_3000.results]
    assert distances == sorted(distances)

    # Empty radius / out of state coordinates (e.g., Delhi)
    res_empty = await service.find_nearby_toilets(latitude=28.6139, longitude=77.2090, radius_meters=1000)
    assert res_empty.success is True
    assert res_empty.total_results == 0
    assert len(res_empty.results) == 0


@pytest.mark.anyio
async def test_stable_ids_and_metadata():
    client = BBMPStaticClient()
    service = ToiletDiscoveryService(overpass_client=client)

    lat, lon = 13.0979, 77.5969
    res1 = await service.find_nearby_toilets(latitude=lat, longitude=lon, radius_meters=2000)
    res2 = await service.find_nearby_toilets(latitude=lat, longitude=lon, radius_meters=2000)

    assert [t.osm_id for t in res1.results] == [t.osm_id for t in res2.results]
    if res1.results:
        first = res1.results[0]
        assert first.source == "BBMP"
        assert first.ward is not None

