"""
Output formatters for Site Scout reports.
Includes verification links (Google Maps, data source URLs) for every result.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List


def format_markdown(results: Dict[str, Any]) -> str:
    """Format results as human-readable report with verification links."""
    coords = results["coordinates"]
    lat, lon = coords["lat"], coords["lon"]
    radius = results["radius_km"]
    ts = results.get("timestamp", "")

    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        time_str = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        time_str = ts

    out: List[str] = []
    a = out.append

    a(f"📍 Site Scout Report — ({lat:.4f}, {lon:.4f})")
    a(f"Generated: {time_str}")
    a(f"🗺️ Google Maps: https://www.google.com/maps?q={lat},{lon}")
    a("")

    # ---- Pipelines ----
    a(f"═══ 🔴 NATURAL GAS PIPELINES ({radius}km radius) ═══")
    a("")

    pipelines = results.get("pipelines", [])
    if pipelines:
        for i, p in enumerate(pipelines[:15], 1):
            op = p.get("operator", "Unknown")
            tag = " ⭐" if p.get("is_target_operator") else ""
            a(f"  #{i}  {op}{tag}")
            a(f"      Distance: {p['distance_km']} km ({p['distance_mi']} mi) — Direction: {p.get('direction', '?')}")
            a(f"      Type: {p.get('type', '?')} | Status: {p.get('status', '?')}")
            nlat = p.get("nearest_point_lat")
            nlon = p.get("nearest_point_lon")
            if nlat and nlon:
                a(f"      📍 Nearest: ({nlat}, {nlon})")
                a(f"      🗺️ {p.get('google_maps_link', '')}")
            eia_url = p.get("eia_record_url")
            if eia_url:
                a(f"      🔗 EIA Record: {eia_url}")
            a(f"      📊 Source: {p.get('data_source', 'EIA')}")
            a("")
    else:
        a("  ❌ No pipelines found within radius")
        a("")

    # ---- Transmission Lines ----
    a(f"═══ 🟡 TRANSMISSION LINES ({radius}km radius) ═══")
    a("")

    tx_lines = results.get("transmission_lines", [])
    if tx_lines:
        for i, t in enumerate(tx_lines[:10], 1):
            owner = t.get("owner", "Unknown")
            v = t.get("voltage_kv", "?")
            a(f"  #{i}  {owner} — {v} kV")
            a(f"      Distance: {t['distance_km']} km ({t['distance_mi']} mi) — Direction: {t.get('direction', '?')} | Status: {t.get('status', '?')}")
            nlat = t.get("nearest_point_lat")
            nlon = t.get("nearest_point_lon")
            if nlat and nlon:
                a(f"      📍 Nearest: ({nlat}, {nlon})")
                a(f"      🗺️ {t.get('google_maps_link', '')}")
            hifld_url = t.get("hifld_record_url")
            if hifld_url:
                a(f"      🔗 HIFLD Record: {hifld_url}")
            a(f"      📊 Source: {t.get('data_source', 'HIFLD')}")
            a("")
    else:
        a("  ❌ No transmission lines found within radius")
        a("")

    # ---- Substations ----
    a(f"═══ 🏭 SUBSTATIONS ({radius}km radius) ═══")
    a("")
    subs = results.get("substations", [])
    if subs:
        for i, s in enumerate(subs[:15], 1):
            name = s.get("name", "Unknown")
            stype = s.get("type", "?")
            status = s.get("status", "?")
            lines = s.get("lines", 0)
            city = s.get("city", "")
            status_icon = "✅" if status == "IN SERVICE" else ("🔨" if "CONSTRUCTION" in (status or "").upper() else "⚪")
            a(f"  #{i}  {name} ({stype}) — {status_icon} {status} | Lines: {lines}")
            a(f"      Distance: {s['distance_km']} km ({s['distance_mi']} mi) — Direction: {s.get('direction', '?')}")
            if city:
                a(f"      City: {city}, {s.get('state', '')}")
            slat = s.get("lat")
            slon = s.get("lon")
            if slat and slon:
                a(f"      📍 ({slat}, {slon})")
                a(f"      🗺️ {s.get('google_maps_link', '')}")
            hifld_url = s.get("hifld_record_url")
            if hifld_url:
                a(f"      🔗 HIFLD Record: {hifld_url}")
            a(f"      📊 Source: {s.get('data_source', 'HIFLD')}")
            a("")
    else:
        a("  ❌ No substations found within radius")
        a("")

    # ---- Fiber ----
    a("═══ 🔵 FIBER / BROADBAND ═══")
    a("")
    fiber = results.get("fiber", {})
    has_fiber = fiber.get("has_fiber")

    if has_fiber is True:
        a("  Status: ✅ Fiber Available")
    elif has_fiber is False:
        a("  Status: ❌ No Fiber")
    else:
        a("  Status: ❓ Unknown")

    block = fiber.get("block_data", {})
    if block:
        total = block.get("total_locations", 0)
        served = block.get("served", 0)
        unserved = block.get("unserved", 0)
        underserved = block.get("underserved", 0)
        a(f"  📍 Census Block: {block.get('geoid', '?')}")
        a(f"  Locations (BSL): {total} total | {served} served | {unserved} unserved | {underserved} underserved")
        a(f"  Fiber served: {block.get('fiber_served', 0)} | Cable: {block.get('cable_served', 0)} | Fixed Wireless: {block.get('fixed_wireless_served', 0)}")
        a(f"  Providers: {block.get('unique_providers', 0)} total | {block.get('fiber_providers', 0)} fiber | {block.get('cable_providers', 0)} cable")

    county = fiber.get("county_data", {})
    if county:
        a(f"  📊 County overview ({block.get('county', '?')}):")
        a(f"     {county.get('total_locations', 0)} BSLs | {county.get('served_pct', 0)}% served | {county.get('fiber_served', 0)} fiber | {county.get('fiber_providers', 0)} fiber ISPs")

    manual = fiber.get("manual_check_url")
    if manual:
        a(f"  🔗 Verify: {manual}")
    a(f"  📊 Source: {fiber.get('data_source', 'FCC BDC')}")
    a("")

    # ---- City Limits ----
    a("═══ 🏙️ CITY LIMITS ═══")
    a("")
    cl = results.get("city_limits", {})
    if cl.get("in_city"):
        a(f"  Status: ✅ Inside City Limits — {cl.get('city_name', '?')}, TX")
    else:
        a("  Status: ❌ Outside City Limits")
    if cl.get("county"):
        a(f"  County: {cl['county']}")
    if cl.get("census_tract"):
        a(f"  Census Tract: {cl['census_tract']}")
    a("  📊 Source: US Census Bureau Geocoder API")
    if cl.get("error"):
        a(f"  ⚠️ {cl['error']}")
    a("")

    # ---- Nearby Cities (boundary distance) ----
    nearby = results.get("nearby_cities", [])
    if nearby:
        a(f"  📏 Distance to Nearest City Boundaries:")
        a("")
        for i, c in enumerate(nearby[:8], 1):
            name = c.get("name", "?")
            ctype = c.get("type", "")
            inside = c.get("inside", False)
            bd = c.get("distance_to_boundary_km", "?")
            bd_mi = c.get("distance_to_boundary_mi", "?")
            cd = c.get("distance_to_center_km", "?")

            if inside:
                a(f"  #{i}  {name} — ✅ INSIDE (boundary {bd} km / {bd_mi} mi away)")
            else:
                a(f"  #{i}  {name} — {bd} km ({bd_mi} mi) to boundary | {cd} km to center")
            blat = c.get("nearest_boundary_lat")
            blon = c.get("nearest_boundary_lon")
            if blat and blon:
                a(f"      📍 Nearest edge: ({blat}, {blon})")
                a(f"      🗺️ {c.get('google_maps_link', '')}")
            a(f"      📊 Source: {c.get('data_source', 'Census TIGERweb')}")
            a("")

    # ---- EPA ----
    a("═══ 🌿 EPA ATTAINMENT ═══")
    a("")
    att = results.get("attainment", {})
    if att.get("attainment", True):
        a("  Status: ✅ Attainment Area")
        a(f"  County: {att.get('county', '?')}")
        a("  All criteria pollutants in attainment")
    else:
        a("  Status: ❌ Nonattainment Area")
        a(f"  County: {att.get('county', '?')}")
        pols = att.get("pollutants_nonattainment", [])
        if pols:
            a(f"  Nonattainment: {', '.join(pols)}")
    a("  📊 Source: EPA Green Book")
    if att.get("error"):
        a(f"  ⚠️ {att['error']}")
    a("")

    # ---- Data Sources Reference ----
    a("═══ 📚 DATA SOURCES (手动查询入口) ═══")
    a("")
    a(f"  管道: https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/Natural_Gas_Interstate_and_Intrastate_Pipelines_1/FeatureServer/0")
    a(f"  输电线: https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0")
    a(f"  变电站: https://services6.arcgis.com/OO2s4OoyCZkYJ6oE/arcgis/rest/services/Substations/FeatureServer/0")
    a(f"  变电站地图: https://www.arcgis.com/apps/mapviewer/index.html?url=https://services6.arcgis.com/OO2s4OoyCZkYJ6oE/arcgis/rest/services/Substations/FeatureServer/0&center={lon},{lat}&level=10")
    a(f"  光纤(FCC BDC): https://services8.arcgis.com/peDZJliSvYims39Q/arcgis/rest/services/FCC_Broadband_Data_Collection_December_2024_View/FeatureServer")
    a(f"  City Limits: https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer/4")
    a(f"  EPA Green Book: https://www.epa.gov/green-book")

    return "\n".join(out)


def format_json(results: Dict[str, Any]) -> str:
    """Format results as clean JSON."""
    clean = {
        "site_scout_version": "1.1.0",
        "query": {
            "coordinates": results["coordinates"],
            "radius_km": results["radius_km"],
            "timestamp": results.get("timestamp"),
        },
        "infrastructure": {
            "pipelines": {
                "count": len(results.get("pipelines", [])),
                "features": results.get("pipelines", []),
            },
            "transmission_lines": {
                "count": len(results.get("transmission_lines", [])),
                "features": results.get("transmission_lines", []),
            },
        },
        "connectivity": {"fiber": results.get("fiber", {})},
        "regulatory": {
            "city_limits": results.get("city_limits", {}),
            "epa_attainment": results.get("attainment", {}),
        },
    }
    return json.dumps(clean, indent=2, ensure_ascii=False)
