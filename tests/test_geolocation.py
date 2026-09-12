"""
Tests for src/geolocation.py. Pure Python + shapely, synthetic fixtures
-- no geopandas/fiona/network needed, matching the module's I/O-boundary
design (see its module docstring).
"""
from shapely.geometry import Polygon

from src.geolocation import (
    match_station_name,
    match_csb_polygon,
    resolve_site_geometry,
    resolve_all_sites,
)

NDSU_FARM = {
    "key": "NDSU Horticulture Research Farm",
    "aliases": ["NDSU Hort Farm", "Absaraka farm"],
    "geometry": Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]),
    "precision_tier": "S",
}
MANDAN_FARM = {
    "key": "Mandan Northern Great Plains Research Lab",
    "aliases": ["Mandan NGPRL", "USDA-ARS Mandan"],
    "geometry": Polygon([(10, 10), (10, 11), (11, 11), (11, 10)]),
    "precision_tier": "A",  # a NAIP-verified plot, not just a farm envelope
}
REGISTRY = [NDSU_FARM, MANDAN_FARM]

CSB_FIELD = {
    "field_id": "CSB-12345",
    "geometry": Polygon([(50, 50), (50, 51), (51, 51), (51, 50)]),
}
CSB_ENTRIES = [CSB_FIELD]


def test_match_station_name_exact():
    assert match_station_name("NDSU Horticulture Research Farm", REGISTRY) is NDSU_FARM


def test_match_station_name_alias_substring():
    # substring containment: a paper's fuller description contains the alias
    hit = match_station_name("field trial at the NDSU Hort Farm site", REGISTRY)
    assert hit is NDSU_FARM


def test_match_station_name_no_match():
    assert match_station_name("Some Unrelated University Farm", REGISTRY) is None


def test_match_station_name_empty_registry():
    assert match_station_name("NDSU Horticulture Research Farm", []) is None


def test_match_csb_polygon_hit():
    hit = match_csb_polygon(50.5, 50.5, CSB_ENTRIES)
    assert hit is CSB_FIELD


def test_match_csb_polygon_miss():
    assert match_csb_polygon(0.5, 0.5, CSB_ENTRIES) is None


def test_resolve_site_geometry_station_wins_over_csb():
    # even if a CSB polygon is ALSO available, a station match takes
    # priority per the confirmed resolution order
    result = resolve_site_geometry(
        "NDSU Horticulture Research Farm", 50.5, 50.5,
        station_registry=REGISTRY, csb_entries=CSB_ENTRIES,
    )
    assert result.geom_source == "station"
    assert result.spatial_tier == "S"
    assert result.matched_key == "NDSU Horticulture Research Farm"


def test_resolve_site_geometry_uses_registry_entrys_own_tier():
    # the registry is not uniformly tier S -- a NAIP-verified entry is A
    result = resolve_site_geometry(
        "Mandan NGPRL", None, None, station_registry=REGISTRY,
    )
    assert result.geom_source == "station"
    assert result.spatial_tier == "A"


def test_resolve_site_geometry_falls_back_to_csb():
    result = resolve_site_geometry(
        "no station name given", 50.5, 50.5,
        station_registry=REGISTRY, csb_entries=CSB_ENTRIES,
    )
    assert result.geom_source == "csb"
    assert result.spatial_tier == "C"
    assert result.matched_key == "CSB-12345"


def test_resolve_site_geometry_falls_to_tier_d():
    result = resolve_site_geometry(
        "totally unknown site", 0.5, 0.5,
        station_registry=REGISTRY, csb_entries=CSB_ENTRIES,
    )
    assert result.geom_source == "none"
    assert result.spatial_tier == "D"
    assert result.geometry_geojson is None


def test_resolve_all_sites_splits_manual_review_queue():
    sites = [
        {"paper_id": 1, "station_name_raw": "NDSU Horticulture Research Farm",
         "latitude": 50.5, "longitude": 50.5},
        {"paper_id": 2, "station_name_raw": "totally unknown site",
         "latitude": 0.5, "longitude": 0.5},
    ]
    resolved, manual_review = resolve_all_sites(sites, station_registry=REGISTRY, csb_entries=CSB_ENTRIES)
    assert len(resolved) == 2
    assert len(manual_review) == 1
    assert manual_review[0]["paper_id"] == 2
    assert resolved[0]["geom_source"] == "station"
