"""
Stage 4 (Geolocation): resolve a research site's geometry from a
station name and/or lat/lon point, per the confirmed matching order in
the "CC maps" project's cc-groundtruth-workflow-v0.md (Stage 4 notes,
2026-09-11):

  1. Station name/alias registry match (built by hand in QGIS/Google
     Earth from repeated station names across papers) -> geom_source
     "station", spatial_tier = that registry entry's OWN precision_tier
     (most entries are "S" = farm-envelope-only; a NAIP-verified entry
     can be "A" -- the registry is not uniformly one tier).
  2. USDA Crop Sequence Boundaries (CSB) point-in-polygon match ->
     geom_source "csb", spatial_tier "C" (never auto-promoted to "B" --
     that requires a human to confirm the treatment covered the whole
     field).
  3. Neither resolves -> geom_source "none", spatial_tier "D", queued
     for manual NAIP review.

Matching logic (match_station_name, match_csb_polygon,
resolve_site_geometry) is pure Python + shapely, decoupled from
geopandas/fiona, which are only used at the file-loading (I/O) boundary
in load_station_registry()/load_csb() -- so this module is unit
testable without those heavier geospatial deps installed, and only
needs them when actually run against real files.
"""
from __future__ import annotations

import json as _json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from shapely.geometry import Point, mapping

# Real paths on CyVerse (confirmed 2026-09-11). stations.gpkg does not
# exist yet -- the user is building it by hand in QGIS/Google Earth.
DEFAULT_CSB_PATH = Path("/home/pengyuwh/Crop Sequence Boundaries")
DEFAULT_STATION_REGISTRY_PATH = Path("/home/pengyuwh/data-store/LLM_AutoExtracting_CC/stations.gpkg")


@dataclass
class SiteGeometryResult:
    geometry_geojson: Optional[str]
    geom_source: str  # "station" | "csb" | "none"
    spatial_tier: str  # "A" | "B" | "C" | "S" | "D"
    matched_key: Optional[str]
    notes: str


def _normalize_name(name: str) -> str:
    name = str(name).lower().strip()
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def match_station_name(station_name_raw: Optional[str], station_registry: list[dict]) -> Optional[dict]:
    """
    Pure matching logic, no I/O. station_registry is a list of dicts,
    each with at least {"key", "aliases": [...], "geometry":
    shapely-geometry-or-None, "precision_tier": "A"|"B"|"C"|"S"}.
    Tries an exact normalized match against the key or any alias first,
    then a substring containment match (handles "KBS" inside "Kellogg
    Biological Station (KBS), Michigan"). Returns the matched registry
    entry dict, or None.
    """
    if not station_name_raw or not station_registry:
        return None
    norm_input = _normalize_name(station_name_raw)
    if not norm_input:
        return None

    for entry in station_registry:
        candidates = [entry.get("key", "")] + list(entry.get("aliases", []))
        norm_candidates = {_normalize_name(c) for c in candidates if c}
        if norm_input in norm_candidates:
            return entry

    for entry in station_registry:
        candidates = [entry.get("key", "")] + list(entry.get("aliases", []))
        for c in candidates:
            norm_c = _normalize_name(c)
            if not norm_c:
                continue
            if norm_c in norm_input or norm_input in norm_c:
                return entry
    return None


def match_csb_polygon(lat: float, lon: float, csb_entries: list[dict]) -> Optional[dict]:
    """
    Pure matching logic, no I/O. csb_entries is a list of dicts, each
    with at least {"field_id", "geometry": shapely-geometry}. Returns
    the first entry whose geometry contains the point, or None.
    """
    if lat is None or lon is None or not csb_entries:
        return None
    point = Point(lon, lat)
    for entry in csb_entries:
        geom = entry.get("geometry")
        if geom is not None and geom.contains(point):
            return entry
    return None


def resolve_site_geometry(
    station_name_raw: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
    *,
    station_registry: list[dict],
    csb_entries: Optional[list[dict]] = None,
) -> SiteGeometryResult:
    """The core per-site resolver -- see module docstring for the order."""
    match = match_station_name(station_name_raw, station_registry)
    if match is not None:
        geom = match.get("geometry")
        return SiteGeometryResult(
            geometry_geojson=_json.dumps(mapping(geom)) if geom is not None else None,
            geom_source="station",
            spatial_tier=match.get("precision_tier") or "S",
            matched_key=match.get("key"),
            notes=f"station registry match: {match.get('key')}",
        )

    if lat is not None and lon is not None and csb_entries:
        csb_hit = match_csb_polygon(lat, lon, csb_entries)
        if csb_hit is not None:
            return SiteGeometryResult(
                geometry_geojson=_json.dumps(mapping(csb_hit["geometry"])),
                geom_source="csb",
                spatial_tier="C",
                matched_key=str(csb_hit.get("field_id")),
                notes="USDA CSB field polygon (point-in-polygon match); "
                      "confirm treatment covers the whole field before promoting to tier B",
            )

    return SiteGeometryResult(
        geometry_geojson=None,
        geom_source="none",
        spatial_tier="D",
        matched_key=None,
        notes="no station registry match and no CSB polygon at this point — "
              "queued for manual NAIP review",
    )


def resolve_all_sites(
    sites: list[dict],
    *,
    station_registry: list[dict],
    csb_entries: Optional[list[dict]] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Batch driver. sites: list of dicts with at least {"station_name_raw",
    "latitude", "longitude"} plus whatever identifying fields the caller
    wants carried through (paper_id, unit_index, ...). Returns
    (resolved, manual_review) -- resolved sites carry their
    SiteGeometryResult fields merged in; manual_review holds only the
    tier-D ones (geom_source == "none"), for the manual-NAIP-review
    queue.
    """
    resolved: list[dict] = []
    manual_review: list[dict] = []
    for site in sites:
        result = resolve_site_geometry(
            site.get("station_name_raw"),
            site.get("latitude"),
            site.get("longitude"),
            station_registry=station_registry,
            csb_entries=csb_entries,
        )
        merged = {**site, **{
            "geometry_geojson": result.geometry_geojson,
            "geom_source": result.geom_source,
            "spatial_tier": result.spatial_tier,
            "matched_key": result.matched_key,
            "notes": result.notes,
        }}
        resolved.append(merged)
        if result.geom_source == "none":
            manual_review.append(merged)
    return resolved, manual_review


# ═══════════════════════════ I/O boundary (geopandas/fiona) ═══════════════
# Only imported/used here -- everything above is testable without them.

def load_station_registry(path: Path = DEFAULT_STATION_REGISTRY_PATH) -> list[dict]:
    """
    Loads stations.gpkg into the plain-dict shape match_station_name()
    expects. Degrades gracefully to an empty registry if the file
    doesn't exist yet (every site then falls through to CSB / tier D).
    Expected columns: key, aliases (comma-separated string), geometry,
    precision_tier.
    """
    path = Path(path)
    if not path.exists():
        return []
    import geopandas as gpd  # noqa: F401 (only needed here)

    gdf = gpd.read_file(path)
    registry = []
    for _, row in gdf.iterrows():
        aliases_raw = row.get("aliases") or ""
        registry.append({
            "key": row.get("key"),
            "aliases": [a.strip() for a in str(aliases_raw).split(",") if a.strip()],
            "geometry": row.geometry,
            "precision_tier": row.get("precision_tier") or "S",
        })
    return registry


def _pick_csb_layer(gdb_path: Path, year: Optional[int] = None) -> str:
    """
    USDA CSB .gdb files hold one layer per year. Layer-naming convention
    is NOT YET VERIFIED against the real file at DEFAULT_CSB_PATH (still
    a TODO on CyVerse) -- this is a best-effort guess (most recent /
    only layer, or one matching `year` by substring) pending that check.
    """
    import fiona  # noqa: F401 (only needed here)

    layers = fiona.listlayers(str(gdb_path))
    if not layers:
        raise ValueError(f"no layers found in {gdb_path}")
    if year is not None:
        for layer in layers:
            if str(year) in layer:
                return layer
    return sorted(layers)[-1]


def load_csb(path: Path = DEFAULT_CSB_PATH, year: Optional[int] = None) -> list[dict]:
    """Loads a CSB layer into the plain-dict shape match_csb_polygon() expects."""
    path = Path(path)
    if not path.exists():
        return []
    import geopandas as gpd  # noqa: F401 (only needed here)

    layer = _pick_csb_layer(path, year)
    gdf = gpd.read_file(path, layer=layer)
    id_col = "CSBID" if "CSBID" in gdf.columns else gdf.columns[0]
    return [
        {"field_id": row[id_col], "geometry": row.geometry}
        for _, row in gdf.iterrows()
    ]
