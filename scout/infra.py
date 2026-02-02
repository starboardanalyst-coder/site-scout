"""
Infrastructure queries for pipelines, substations/transmission lines, and fiber.

Data sources:
  - Pipelines: EIA Natural Gas Interstate and Intrastate Pipelines (ArcGIS)
  - Transmission: HIFLD Electric Power Transmission Lines (ArcGIS)
  - Fiber: FCC Broadband Map (manual link; API endpoint unstable)
"""

import requests
import json
import os
import math
from typing import List, Dict, Any, Tuple, Optional
from .geo_utils import haversine_distance, km_to_miles, compass_direction


CACHE_DIR = "cache"

# ---- Verified working API endpoints (Feb 2026) ----
PIPELINE_URL = (
    "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
    "Natural_Gas_Interstate_and_Intrastate_Pipelines_1/FeatureServer/0/query"
)
TRANSMISSION_URL = (
    "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/"
    "Electric_Power_Transmission_Lines/FeatureServer/0/query"
)
FCC_BROADBAND_VIEWER = (
    "https://broadbandmap.fcc.gov/location-summary/fixed"
    "?speed=25&latency=0&satellite=true&lat={lat}&lon={lon}"
)


def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def _nearest_on_paths(plat: float, plon: float,
                      paths: List[List]) -> Tuple[float, Optional[Tuple[float, float]]]:
    """Find nearest point on a set of paths to the given lat/lon."""
    mind = 999999
    nearest = None
    for path in paths:
        for c in path:
            d = haversine_distance(plat, plon, c[1], c[0])
            if d < mind:
                mind = d
                nearest = (c[1], c[0])  # (lat, lon)
    return mind, nearest


def _google_maps_link(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"


# ============================================================
# Pipelines — EIA Natural Gas Pipelines
# ============================================================

def query_pipelines(lat: float, lon: float, radius_km: float,
                    operators: Optional[List[str]] = None,
                    include_all: bool = True) -> List[Dict[str, Any]]:
    """
    Query EIA ArcGIS for natural gas pipelines near a point.

    Args:
        lat, lon: Coordinates.
        radius_km: Search radius.
        operators: Filter to these operators (e.g. ["Kinder Morgan", "Targa"]).
                   If include_all=True, also returns non-matching pipelines.
        include_all: If True, return all pipelines + flag target operators.

    Returns:
        Sorted list of pipeline dicts with distances and verification links.
    """
    ensure_cache_dir()
    geometry = json.dumps({
        "x": lon, "y": lat,
        "spatialReference": {"wkid": 4326}
    })

    params = {
        "f": "json",
        "geometry": geometry,
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": radius_km,
        "units": "esriSRUnit_Kilometer",
        "outFields": "Operator,TYPEPIPE,Status",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultRecordCount": 100,
    }

    # Optionally filter by operator
    if operators and not include_all:
        clauses = [f"Operator LIKE '%{op}%'" for op in operators]
        params["where"] = " OR ".join(clauses)
    else:
        params["where"] = "1=1"

    try:
        resp = requests.get(PIPELINE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("error"):
            print(f"Warning: Pipeline API error: {data['error'].get('message')}")
            return []

        results = []
        seen = set()
        target_ops = [o.lower() for o in (operators or [])]

        for feat in data.get("features", []):
            attrs = feat["attributes"]
            geom = feat.get("geometry", {})
            paths = geom.get("paths", [])
            if not paths:
                continue

            dist, nearest = _nearest_on_paths(lat, lon, paths)
            if nearest is None:
                continue

            operator = attrs.get("Operator", "Unknown")
            dedup_key = f"{operator}_{round(dist, 0)}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            is_target = any(t in operator.lower() for t in target_ops) if target_ops else False
            nlat, nlon = nearest

            results.append({
                "operator": operator,
                "type": attrs.get("TYPEPIPE", "Unknown"),
                "status": attrs.get("Status", "Unknown"),
                "distance_km": round(dist, 1),
                "distance_mi": round(km_to_miles(dist), 1),
                "nearest_point_lat": round(nlat, 6),
                "nearest_point_lon": round(nlon, 6),
                "direction": compass_direction(lat, lon, nlat, nlon),
                "is_target_operator": is_target,
                "google_maps_link": _google_maps_link(nlat, nlon),
                "data_source": "EIA Natural Gas Interstate & Intrastate Pipelines (ArcGIS FeatureServer)",
            })

        results.sort(key=lambda x: x["distance_km"])
        return results

    except Exception as e:
        print(f"Warning: Pipeline query failed: {e}")
        return []


# ============================================================
# Transmission Lines — HIFLD Electric Power Transmission Lines
# ============================================================

def query_transmission_lines(lat: float, lon: float, radius_km: float,
                             min_voltage_kv: int = 69) -> List[Dict[str, Any]]:
    """
    Query HIFLD for electric power transmission lines near a point.

    Note: HIFLD substations endpoint no longer available (2026).
    Using transmission lines as the best available proxy for grid access points.
    """
    ensure_cache_dir()

    # Convert to Web Mercator for spatial query
    x = lon * 20037508.34 / 180
    y_rad = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y_rad * 20037508.34 / 180
    buf = radius_km * 1000  # meters

    params = {
        "f": "json",
        "geometry": f"{x - buf},{y - buf},{x + buf},{y + buf}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "3857",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "OWNER,VOLTAGE,VOLT_CLASS,STATUS",
        "returnGeometry": "true",
        "resultRecordCount": 100,
    }

    try:
        resp = requests.get(TRANSMISSION_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("error"):
            print(f"Warning: Transmission API error: {data['error'].get('message')}")
            return []

        results = []
        seen = set()

        for feat in data.get("features", []):
            attrs = feat["attributes"]
            geom = feat.get("geometry", {})
            paths = geom.get("paths", [])
            if not paths:
                continue

            voltage = attrs.get("VOLTAGE", 0)
            try:
                voltage = int(str(voltage).replace("kV", "").strip())
            except (ValueError, TypeError):
                voltage = 0
            if voltage < min_voltage_kv:
                continue

            dist, nearest = _nearest_on_paths(lat, lon, paths)
            if nearest is None:
                continue

            owner = attrs.get("OWNER", "Unknown")
            dedup_key = f"{owner}_{voltage}_{round(dist, 0)}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            nlat, nlon = nearest
            results.append({
                "owner": owner,
                "voltage_kv": voltage,
                "volt_class": attrs.get("VOLT_CLASS", ""),
                "status": attrs.get("STATUS", "Unknown"),
                "distance_km": round(dist, 1),
                "distance_mi": round(km_to_miles(dist), 1),
                "nearest_point_lat": round(nlat, 6),
                "nearest_point_lon": round(nlon, 6),
                "direction": compass_direction(lat, lon, nlat, nlon),
                "google_maps_link": _google_maps_link(nlat, nlon),
                "data_source": "HIFLD Electric Power Transmission Lines (ArcGIS FeatureServer)",
            })

        results.sort(key=lambda x: x["distance_km"])
        return results

    except Exception as e:
        print(f"Warning: Transmission query failed: {e}")
        return []


# ============================================================
# Fiber / Broadband — FCC
# ============================================================

def query_fiber(lat: float, lon: float) -> Dict[str, Any]:
    """
    Return FCC broadband info. Direct API is unstable (405 errors as of Feb 2026).
    Returns a manual verification link instead.
    """
    viewer_url = FCC_BROADBAND_VIEWER.format(lat=lat, lon=lon)
    return {
        "has_fiber": None,  # Cannot determine programmatically
        "providers": [],
        "max_download_mbps": 0,
        "max_upload_mbps": 0,
        "technology_types": [],
        "manual_check_url": viewer_url,
        "data_source": "FCC Broadband Map",
        "note": "FCC API不稳定，请手动验证: " + viewer_url,
    }
