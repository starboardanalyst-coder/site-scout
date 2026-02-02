"""
Output formatters for Site Scout reports
"""

import json
from datetime import datetime
from typing import Dict, Any, List


def format_markdown(results: Dict[str, Any]) -> str:
    """
    Format results as human-readable markdown report
    """
    coords = results['coordinates']
    lat, lon = coords['lat'], coords['lon']
    radius = results['radius_km']
    timestamp = results['timestamp']
    
    # Parse timestamp for display
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_str = dt.strftime("%Y-%m-%d %H:%M UTC")
    except:
        time_str = timestamp
    
    # Start building the report
    report = []
    report.append(f"📍 Site Scout Report — ({lat:.4f}, {lon:.4f})")
    report.append(f"Generated: {time_str}")
    report.append("")
    
    # Natural Gas Pipelines Section
    report.append(f"═══ 🔴 NATURAL GAS PIPELINES ({radius}km radius) ═══")
    report.append("")
    
    pipelines = results.get('pipelines', [])
    if pipelines:
        for i, pipeline in enumerate(pipelines[:10], 1):  # Limit to top 10
            name = pipeline.get('name', 'Unknown Pipeline')
            operator = pipeline.get('operator', 'Unknown Operator')
            pipe_type = pipeline.get('type', 'Unknown Type')
            dist_km = pipeline.get('distance_km', 0)
            dist_mi = pipeline.get('distance_mi', 0)
            direction = pipeline.get('direction', 'Unknown')
            
            report.append(f"  #{i}  {name} ({operator})")
            report.append(f"      Distance: {dist_km} km ({dist_mi} mi) — Direction: {direction}")
            report.append(f"      Type: {pipe_type}")
            report.append("")
    else:
        report.append("  ❌ No Kinder Morgan or Targa pipelines found within radius")
        report.append("")
    
    # Electric Substations Section
    report.append(f"═══ 🟡 ELECTRIC SUBSTATIONS ({radius}km radius) ═══")
    report.append("")
    
    substations = results.get('substations', [])
    if substations:
        for i, substation in enumerate(substations[:10], 1):  # Limit to top 10
            name = substation.get('name', 'Unknown Substation')
            voltage = substation.get('voltage_kv', 0)
            dist_km = substation.get('distance_km', 0)
            dist_mi = substation.get('distance_mi', 0)
            direction = substation.get('direction', 'Unknown')
            
            report.append(f"  #{i}  {name}")
            report.append(f"      Distance: {dist_km} km ({dist_mi} mi) — {voltage} kV — Direction: {direction}")
            report.append("")
    else:
        report.append("  ❌ No substations found within radius")
        report.append("")
    
    # Fiber / Broadband Section
    report.append("═══ 🔵 FIBER / BROADBAND ═══")
    report.append("")
    
    fiber = results.get('fiber', {})
    has_fiber = fiber.get('has_fiber', False)
    providers = fiber.get('providers', [])
    max_down = fiber.get('max_download_mbps', 0)
    max_up = fiber.get('max_upload_mbps', 0)
    
    if has_fiber:
        report.append("  Status: ✅ Fiber Available")
        if providers:
            providers_str = ", ".join(providers[:5])  # Limit provider list
            report.append(f"  Providers: {providers_str}")
        if max_down > 0 and max_up > 0:
            report.append(f"  Max Speed: {max_down}/{max_up} Mbps")
    else:
        report.append("  Status: ❌ No Fiber Detected")
        if providers:
            providers_str = ", ".join(providers[:5])
            report.append(f"  Other Providers: {providers_str}")
    
    if 'error' in fiber:
        report.append(f"  ⚠️  Query Error: {fiber['error']}")
    
    report.append("")
    
    # City Limits Section
    report.append("═══ 🏙️ CITY LIMITS ═══")
    report.append("")
    
    city_limits = results.get('city_limits', {})
    in_city = city_limits.get('in_city', False)
    city_name = city_limits.get('city_name')
    county = city_limits.get('county')
    state = city_limits.get('state')
    
    if in_city and city_name:
        report.append(f"  Status: ✅ Inside City Limits")
        report.append(f"  City: {city_name}, {state or 'TX'}")
    else:
        report.append("  Status: ❌ Outside City Limits")
        if city_name:
            report.append(f"  Nearest City: {city_name}, {state or 'TX'}")
    
    if county:
        report.append(f"  County: {county}")
    
    if 'error' in city_limits:
        report.append(f"  ⚠️  Query Error: {city_limits['error']}")
    
    report.append("")
    
    # EPA Attainment Section
    report.append("═══ 🌿 EPA ATTAINMENT ═══")
    report.append("")
    
    attainment = results.get('attainment', {})
    is_attainment = attainment.get('attainment', True)
    county_name = attainment.get('county', 'Unknown County')
    pollutants = attainment.get('pollutants_nonattainment', [])
    
    if is_attainment:
        report.append("  Status: ✅ Attainment Area")
        report.append(f"  County: {county_name}")
        report.append("  All criteria pollutants in attainment")
    else:
        report.append("  Status: ❌ Nonattainment Area")
        report.append(f"  County: {county_name}")
        if pollutants:
            pollutants_str = ", ".join(pollutants)
            report.append(f"  Nonattainment Pollutants: {pollutants_str}")
    
    if 'error' in attainment:
        report.append(f"  ⚠️  Query Error: {attainment['error']}")
    
    return "\n".join(report)


def format_json(results: Dict[str, Any]) -> str:
    """
    Format results as clean JSON output
    """
    # Clean up the results for JSON output
    clean_results = {
        'site_scout_version': '1.0.0',
        'query': {
            'coordinates': results['coordinates'],
            'radius_km': results['radius_km'],
            'timestamp': results['timestamp']
        },
        'infrastructure': {
            'pipelines': {
                'count': len(results.get('pipelines', [])),
                'features': results.get('pipelines', [])
            },
            'substations': {
                'count': len(results.get('substations', [])),
                'features': results.get('substations', [])
            }
        },
        'connectivity': {
            'fiber': results.get('fiber', {})
        },
        'regulatory': {
            'city_limits': results.get('city_limits', {}),
            'epa_attainment': results.get('attainment', {})
        }
    }
    
    return json.dumps(clean_results, indent=2, ensure_ascii=False)


def format_summary_stats(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate summary statistics for the results
    """
    pipelines = results.get('pipelines', [])
    substations = results.get('substations', [])
    fiber = results.get('fiber', {})
    city_limits = results.get('city_limits', {})
    attainment = results.get('attainment', {})
    
    stats = {
        'infrastructure_count': {
            'pipelines': len(pipelines),
            'substations': len(substations)
        },
        'nearest_distances_km': {},
        'connectivity_score': 0,  # 0-100 score
        'regulatory_flags': []
    }
    
    # Calculate nearest distances
    if pipelines:
        stats['nearest_distances_km']['pipeline'] = min(p.get('distance_km', float('inf')) for p in pipelines)
    
    if substations:
        stats['nearest_distances_km']['substation'] = min(s.get('distance_km', float('inf')) for s in substations)
    
    # Connectivity score (simple heuristic)
    score = 0
    if fiber.get('has_fiber'):
        score += 40
    if fiber.get('max_download_mbps', 0) >= 100:
        score += 30
    if len(fiber.get('providers', [])) > 1:
        score += 20
    if len(pipelines) > 0:
        score += 5
    if len(substations) > 0:
        score += 5
    
    stats['connectivity_score'] = min(score, 100)
    
    # Regulatory flags
    if not attainment.get('attainment', True):
        pollutants = attainment.get('pollutants_nonattainment', [])
        stats['regulatory_flags'].append(f"EPA Nonattainment: {', '.join(pollutants)}")
    
    if city_limits.get('in_city'):
        stats['regulatory_flags'].append("Within City Limits")
    
    return stats