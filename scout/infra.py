"""
Infrastructure queries for pipelines, substations, transmission lines, fiber, and city limits.

Data sources:
  - Pipelines: EIA Natural Gas Interstate and Intrastate Pipelines (ArcGIS)
  - Transmission: HIFLD Electric Power Transmission Lines (ArcGIS)
  - Substations: HIFLD Electric Substations (ArcGIS, Jan 2025 update)
  - Fiber: FCC BDC Dec 2024 via ArcGIS (census block level)
  - City Limits: Census TIGERweb Incorporated Places (polygon boundaries)
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
        "outFields": "FID,Operator,TYPEPIPE,Status",
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
            fid = attrs.get("FID")
            eia_url = (
                f"https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
                f"Natural_Gas_Interstate_and_Intrastate_Pipelines_1/FeatureServer/0/"
                f"query?where=FID={fid}&outFields=*&f=html"
            ) if fid else None

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
                "eia_record_url": eia_url,
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
        "outFields": "OBJECTID_1,OWNER,VOLTAGE,VOLT_CLASS,STATUS",
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
            oid = attrs.get("OBJECTID_1")
            hifld_url = (
                f"https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/"
                f"Electric_Power_Transmission_Lines/FeatureServer/0/"
                f"query?where=OBJECTID_1={oid}&outFields=*&f=html"
            ) if oid else None

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
                "hifld_record_url": hifld_url,
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

FCC_BDC_URL = (
    "https://services8.arcgis.com/peDZJliSvYims39Q/arcgis/rest/services/"
    "FCC_Broadband_Data_Collection_December_2024_View/FeatureServer"
)


def query_fiber(lat: float, lon: float) -> Dict[str, Any]:
    """
    Query FCC Broadband Data Collection via ArcGIS (census block level).
    This bypasses the locked-down FCC API by using the public ArcGIS mirror.
    Data: Dec 2024 BDC, block-level BSL (Broadband Serviceable Location) counts.
    """
    viewer_url = FCC_BROADBAND_VIEWER.format(lat=lat, lon=lon)
    geometry = json.dumps({
        "x": lon, "y": lat,
        "spatialReference": {"wkid": 4326}
    })

    result = {
        "has_fiber": None,
        "providers": [],
        "block_data": {},
        "county_data": {},
        "manual_check_url": viewer_url,
        "data_source": "FCC BDC Dec 2024 (ArcGIS FeatureServer, census block level)",
    }

    # ---- Block-level query (point-in-polygon) ----
    try:
        resp = requests.get(f"{FCC_BDC_URL}/4/query", params={
            "f": "json",
            "geometry": geometry,
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": (
                "GEOID,CountyName,StateName,TotalBSLs,ServedBSLs,"
                "UnservedBSLs,UnderservedBSLs,"
                "ServedBSLsFiber,ServedBSLsCable,ServedBSLsCopper,ServedBSLsLTFW,"
                "UniqueProviders,UniqueProvidersFiber,UniqueProvidersCable"
            ),
            "returnGeometry": "false",
        }, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        for feat in data.get("features", []):
            a = feat["attributes"]
            total = a.get("TotalBSLs", 0) or 0
            served = a.get("ServedBSLs", 0) or 0
            fiber = a.get("ServedBSLsFiber", 0) or 0
            cable = a.get("ServedBSLsCable", 0) or 0
            copper = a.get("ServedBSLsCopper", 0) or 0
            ltfw = a.get("ServedBSLsLTFW", 0) or 0  # Licensed/Terrestrial Fixed Wireless

            result["has_fiber"] = fiber > 0
            result["block_data"] = {
                "geoid": a.get("GEOID"),
                "county": a.get("CountyName"),
                "total_locations": total,
                "served": served,
                "unserved": a.get("UnservedBSLs", 0) or 0,
                "underserved": a.get("UnderservedBSLs", 0) or 0,
                "fiber_served": fiber,
                "cable_served": cable,
                "copper_served": copper,
                "fixed_wireless_served": ltfw,
                "unique_providers": a.get("UniqueProviders", 0) or 0,
                "fiber_providers": a.get("UniqueProvidersFiber", 0) or 0,
                "cable_providers": a.get("UniqueProvidersCable", 0) or 0,
            }
    except Exception as e:
        result["block_error"] = str(e)

    # ---- County-level query for broader context ----
    county_name = result.get("block_data", {}).get("county")
    if county_name:
        try:
            resp2 = requests.get(f"{FCC_BDC_URL}/1/query", params={
                "f": "json",
                "where": f"CountyName='{county_name}' AND StateName='Texas'",
                "outFields": (
                    "TotalBSLs,ServedBSLs,ServedBSLsFiber,ServedBSLsCable,"
                    "UniqueProviders,UniqueProvidersFiber"
                ),
                "returnGeometry": "false",
            }, timeout=15)
            resp2.raise_for_status()
            d2 = resp2.json()
            for feat in d2.get("features", []):
                a = feat["attributes"]
                ct = a.get("TotalBSLs", 0) or 0
                cs = a.get("ServedBSLs", 0) or 0
                result["county_data"] = {
                    "total_locations": ct,
                    "served": cs,
                    "served_pct": round(cs / ct * 100, 1) if ct else 0,
                    "fiber_served": a.get("ServedBSLsFiber", 0) or 0,
                    "unique_providers": a.get("UniqueProviders", 0) or 0,
                    "fiber_providers": a.get("UniqueProvidersFiber", 0) or 0,
                }
        except Exception:
            pass

    return result


# ============================================================
# Substations — EIA Power Plants (as proxy for grid access)
# ============================================================

SUBSTATIONS_URL = (
    "https://services6.arcgis.com/OO2s4OoyCZkYJ6oE/arcgis/rest/services/"
    "Substations/FeatureServer/0/query"
)

CITY_LIMITS_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"
    "Places_CouSub_ConCity_SubMCD/MapServer/4/query"
)


def query_substations(lat: float, lon: float, radius_km: float) -> List[Dict[str, Any]]:
    """
    Query HIFLD Electric Substations (Jan 2025 update).
    Returns real substations with type, status, and connected line count.
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
        "outFields": "OBJECTID,ID,NAME,CITY,STATE,TYPE,STATUS,COUNTY,LATITUDE,LONGITUDE,LINES,SOURCE,SOURCEDATE",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultRecordCount": 30,
    }

    try:
        resp = requests.get(SUBSTATIONS_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("error"):
            return []

        results = []
        for feat in data.get("features", []):
            attrs = feat["attributes"]
            slat = attrs.get("LATITUDE")
            slon = attrs.get("LONGITUDE")
            if not slat or not slon:
                geom = feat.get("geometry", {})
                slat = geom.get("y")
                slon = geom.get("x")
            if not slat or not slon:
                continue

            dist = haversine_distance(lat, lon, slat, slon)
            name = attrs.get("NAME", "Unknown")
            oid = attrs.get("OBJECTID")
            hifld_url = (
                f"https://services6.arcgis.com/OO2s4OoyCZkYJ6oE/arcgis/rest/services/"
                f"Substations/FeatureServer/0/query?where=OBJECTID={oid}&outFields=*&f=html"
            ) if oid else None
            results.append({
                "name": name,
                "type": attrs.get("TYPE", "Unknown"),
                "status": attrs.get("STATUS", "Unknown"),
                "lines": attrs.get("LINES", 0) or 0,
                "city": attrs.get("CITY", ""),
                "county": attrs.get("COUNTY", ""),
                "state": attrs.get("STATE", ""),
                "source": attrs.get("SOURCE", ""),
                "source_date": attrs.get("SOURCEDATE", ""),
                "distance_km": round(dist, 1),
                "distance_mi": round(km_to_miles(dist), 1),
                "lat": round(slat, 6),
                "lon": round(slon, 6),
                "direction": compass_direction(lat, lon, slat, slon),
                "google_maps_link": _google_maps_link(slat, slon),
                "hifld_record_url": hifld_url,
                "data_source": "HIFLD Electric Substations (ArcGIS, Jan 2025)",
            })

        results.sort(key=lambda x: x["distance_km"])
        return results

    except Exception as e:
        print(f"Warning: Substations query failed: {e}")
        return []


def query_city_limits_distance(lat: float, lon: float, radius_km: float = 50) -> List[Dict[str, Any]]:
    """
    Query Census TIGERweb for nearby incorporated places (cities/towns).
    Uses Shapely to compute distance to the actual city boundary polygon,
    not just the centroid.
    """
    from shapely.geometry import Point, Polygon
    from shapely.ops import nearest_points

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
        "outFields": "NAME,BASENAME,LSADC,FUNCSTAT,CENTLAT,CENTLON",
        "returnGeometry": "true",
        "outSR": "4326",
    }

    try:
        resp = requests.get(CITY_LIMITS_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if data.get("error"):
            return []

        query_pt = Point(lon, lat)
        results = []

        for feat in data.get("features", []):
            attrs = feat["attributes"]
            rings = feat.get("geometry", {}).get("rings", [])
            if not rings:
                continue

            try:
                poly = Polygon(rings[0], rings[1:] if len(rings) > 1 else [])
                inside = poly.contains(query_pt)

                # Distance to nearest boundary edge
                np_on_edge = nearest_points(query_pt, poly.exterior)[1]
                edge_dist = haversine_distance(lat, lon, np_on_edge.y, np_on_edge.x)

                centlat = float(str(attrs.get("CENTLAT", "0")).replace("+", ""))
                centlon = float(str(attrs.get("CENTLON", "0")).replace("+", ""))
                center_dist = haversine_distance(lat, lon, centlat, centlon)

                results.append({
                    "name": attrs.get("NAME", "Unknown"),
                    "type": attrs.get("LSADC", ""),
                    "inside": inside,
                    "distance_to_boundary_km": round(edge_dist, 1),
                    "distance_to_boundary_mi": round(km_to_miles(edge_dist), 1),
                    "distance_to_center_km": round(center_dist, 1),
                    "nearest_boundary_lat": round(np_on_edge.y, 6),
                    "nearest_boundary_lon": round(np_on_edge.x, 6),
                    "google_maps_link": _google_maps_link(np_on_edge.y, np_on_edge.x),
                    "data_source": "US Census TIGERweb Incorporated Places",
                })
            except Exception:
                continue

        results.sort(key=lambda x: x["distance_to_boundary_km"])
        return results

    except Exception as e:
        print(f"Warning: City limits query failed: {e}")
        return []
