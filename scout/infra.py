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
    """
    Find the true nearest point on polyline paths using Shapely projection.
    This projects onto line segments (not just vertices), giving <100m accuracy
    vs the ~3km error of vertex-only approach.
    """
    from shapely.geometry import Point, LineString, MultiLineString
    from shapely.ops import nearest_points

    query_pt = Point(plon, plat)  # Shapely uses (x=lon, y=lat)
    best_dist = 999999
    best_nearest = None

    for path in paths:
        if len(path) < 2:
            # Single point — fall back to direct distance
            if path:
                c = path[0]
                d = haversine_distance(plat, plon, c[1], c[0])
                if d < best_dist:
                    best_dist = d
                    best_nearest = (c[1], c[0])
            continue

        try:
            line = LineString(path)  # path coords are (lon, lat)
            np_on_line = nearest_points(query_pt, line)[1]
            d = haversine_distance(plat, plon, np_on_line.y, np_on_line.x)
            if d < best_dist:
                best_dist = d
                best_nearest = (np_on_line.y, np_on_line.x)  # (lat, lon)
        except Exception:
            # Fallback to vertex method if Shapely fails
            for c in path:
                d = haversine_distance(plat, plon, c[1], c[0])
                if d < best_dist:
                    best_dist = d
                    best_nearest = (c[1], c[0])

    return best_dist, best_nearest


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
    Query FCC broadband data via browser scraping fallback.
    Direct API returns 405 as of Feb 2026 — we scrape the summary page.
    """
    viewer_url = FCC_BROADBAND_VIEWER.format(lat=lat, lon=lon)

    # Try scraping the FCC broadband map page for ISP data
    try:
        page_url = (
            f"https://broadbandmap.fcc.gov/location-summary/fixed"
            f"?speed=25&latency=0&satellite=true&lat={lat}&lon={lon}&zoom=14"
        )
        resp = requests.get(page_url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; SiteScout/1.0)"
        })
        text = resp.text

        # Extract provider data from embedded JSON in page
        import re
        providers = set()
        # Look for provider names in the page source
        for m in re.finditer(r'"provider_name"\s*:\s*"([^"]+)"', text):
            providers.add(m.group(1))
        for m in re.finditer(r'"dba_name"\s*:\s*"([^"]+)"', text):
            providers.add(m.group(1))

        has_fiber = False
        techs = set()
        for m in re.finditer(r'"technology_code"\s*:\s*(\d+)', text):
            code = int(m.group(1))
            techs.add(code)
            if code in (50, 70):  # 50 = Fiber to Premises, 70 = Fiber
                has_fiber = True

        if providers:
            return {
                "has_fiber": has_fiber,
                "providers": sorted(providers),
                "technology_codes": sorted(techs),
                "max_download_mbps": 0,
                "max_upload_mbps": 0,
                "manual_check_url": viewer_url,
                "data_source": "FCC Broadband Map (page scrape)",
            }
    except Exception as e:
        pass

    # Fallback: return manual check link
    return {
        "has_fiber": None,
        "providers": [],
        "max_download_mbps": 0,
        "max_upload_mbps": 0,
        "manual_check_url": viewer_url,
        "data_source": "FCC Broadband Map",
        "note": "无法自动查询，请手动验证: " + viewer_url,
    }


# ============================================================
# Substations — EIA Power Plants (as proxy for grid access)
# ============================================================

POWER_PLANTS_URL = (
    "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
    "Power_Plants_in_the_US/FeatureServer/0/query"
)


def query_substations(lat: float, lon: float, radius_km: float) -> List[Dict[str, Any]]:
    """
    Query EIA power plants as a proxy for grid access points / substations.
    HIFLD substation endpoint was retired. Power plants indicate grid infrastructure.
    """
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
        "where": "1=1",
        "outFields": "Plant_Name,State,County,Total_MW,Install_MW,PrimSource,Latitude,Longitude",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultRecordCount": 20,
    }

    try:
        resp = requests.get(POWER_PLANTS_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("error"):
            return []

        results = []
        for feat in data.get("features", []):
            attrs = feat["attributes"]
            geom = feat.get("geometry", {})
            slat = geom.get("y") or attrs.get("Latitude")
            slon = geom.get("x") or attrs.get("Longitude")
            if not slat or not slon:
                continue

            dist = haversine_distance(lat, lon, slat, slon)
            results.append({
                "name": attrs.get("Plant_Name", "Unknown"),
                "capacity_mw": attrs.get("Total_MW") or attrs.get("Install_MW") or 0,
                "primary_source": attrs.get("PrimSource", "Unknown"),
                "county": attrs.get("County", ""),
                "distance_km": round(dist, 1),
                "distance_mi": round(km_to_miles(dist), 1),
                "lat": round(slat, 6),
                "lon": round(slon, 6),
                "direction": compass_direction(lat, lon, slat, slon),
                "google_maps_link": _google_maps_link(slat, slon),
                "data_source": "EIA Power Plants (ArcGIS FeatureServer)",
            })

        results.sort(key=lambda x: x["distance_km"])
        return results

    except Exception as e:
        print(f"Warning: Substations/power plants query failed: {e}")
        return []
