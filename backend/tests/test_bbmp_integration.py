import pytest
from app.modules.discovery.bbmp_loader import load_bbmp_records
from app.modules.discovery.bbmp_client import BBMPStaticClient
from app.modules.discovery.service import ToiletDiscoveryService


def test_bbmp_loader_parses_csv():
    records = load_bbmp_records()
    assert len(records) > 0
    first = records[0]
    assert first.latitude > 12.0
    assert first.longitude > 76.0
    assert first.ward_name is not None or first.ward_no is not None
    assert isinstance(first.has_gents, (bool, type(None)))
    assert isinstance(first.has_ladies, (bool, type(None)))


@pytest.mark.anyio
async def test_bbmp_discovery_service():
    client = BBMPStaticClient()
    service = ToiletDiscoveryService(overpass_client=client)

    # Coordinates near Yelahanka / Central Bengaluru
    res = await service.find_nearby_toilets(latitude=13.0979, longitude=77.5969, radius_meters=5000)
    assert res.success is True
    assert res.total_results > 0
    assert res.source == "BBMP"
    first = res.results[0]
    assert first.ward is not None
    assert first.source == "BBMP"

