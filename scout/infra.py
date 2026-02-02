"""
Infrastructure queries for pipelines, substations, and fiber
"""

import requests
import json
import os
from typing import List, Dict, Any
from .geo_utils import haversine_distance, km_to_miles, compass_direction, create_bbox_from_point


# Cache directory for infrastructure data
CACHE_DIR = "cache"


def ensure_cache_dir():
    """Create cache directory if it doesn't exist"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def query_pipelines(lat: float, lon: float, radius_km: float) -> List[Dict[str, Any]]:
    """
    Query EIA ArcGIS REST API for natural gas pipelines within radius
    Returns list of pipeline features with distance calculations
    """
    ensure_cache_dir()
    
    # Create spatial filter - use point buffer for spatial query
    geometry = {
        "x": lon,
        "y": lat,
        "spatialReference": {"wkid": 4326}
    }
    
    # ArcGIS REST API endpoint for Natural Gas Pipelines
    url = "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Natural_Gas_Pipelines/FeatureServer/0/query"
    
    params = {
        'f': 'json',
        'geometry': json.dumps(geometry),
        'geometryType': 'esriGeometryPoint',
        'inSR': 4326,
        'spatialRel': 'esriSpatialRelIntersects',
        'distance': radius_km,
        'units': 'esriSRUnit_Kilometer',
        'outFields': '*',
        'returnGeometry': True,
        'where': "(OPERATOR LIKE '%Kinder Morgan%' OR OPERATOR LIKE '%Targa%')"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        pipelines = []
        
        if 'features' in data:
            for feature in data['features']:
                attrs = feature['attributes']
                geom = feature['geometry']
                
                # Calculate distance to nearest point on pipeline
                # For simplicity, we'll use the first coordinate pair
                if geom and 'paths' in geom and geom['paths']:
                    pipeline_coords = geom['paths'][0]
                    if pipeline_coords:
                        # Find closest point (simplified - just use first point)
                        pipe_lon, pipe_lat = pipeline_coords[0]
                        distance_km = haversine_distance(lat, lon, pipe_lat, pipe_lon)
                        direction = compass_direction(lat, lon, pipe_lat, pipe_lon)
                        
                        pipeline = {
                            'name': attrs.get('PROJ_NAME', 'Unknown Pipeline'),
                            'operator': attrs.get('OPERATOR', 'Unknown Operator'),
                            'type': attrs.get('TYPE', 'Unknown Type'),
                            'distance_km': round(distance_km, 1),
                            'distance_mi': round(km_to_miles(distance_km), 1),
                            'nearest_point_lat': pipe_lat,
                            'nearest_point_lon': pipe_lon,
                            'direction': direction
                        }
                        pipelines.append(pipeline)
        
        # Sort by distance and return
        pipelines.sort(key=lambda x: x['distance_km'])
        return pipelines
        
    except Exception as e:
        print(f"Warning: Pipeline query failed: {e}")
        return []


def query_substations(lat: float, lon: float, radius_km: float) -> List[Dict[str, Any]]:
    """
    Query HIFLD ArcGIS REST API for electric substations within radius
    Returns list of substation features with distance calculations
    """
    ensure_cache_dir()
    
    # Create spatial filter
    geometry = {
        "x": lon,
        "y": lat,
        "spatialReference": {"wkid": 4326}
    }
    
    # ArcGIS REST API endpoint for Electric Substations
    url = "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Substations/FeatureServer/0/query"
    
    params = {
        'f': 'json',
        'geometry': json.dumps(geometry),
        'geometryType': 'esriGeometryPoint',
        'inSR': 4326,
        'spatialRel': 'esriSpatialRelIntersects',
        'distance': radius_km,
        'units': 'esriSRUnit_Kilometer',
        'outFields': '*',
        'returnGeometry': True,
        'where': "STATE = 'TX' AND MAX_VOLT >= 69"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        substations = []
        
        if 'features' in data:
            for feature in data['features']:
                attrs = feature['attributes']
                geom = feature['geometry']
                
                if geom and 'x' in geom and 'y' in geom:
                    sub_lat, sub_lon = geom['y'], geom['x']
                    distance_km = haversine_distance(lat, lon, sub_lat, sub_lon)
                    direction = compass_direction(lat, lon, sub_lat, sub_lon)
                    
                    substation = {
                        'name': attrs.get('SUB_NAME', 'Unknown Substation'),
                        'voltage_kv': attrs.get('MAX_VOLT', 0),
                        'status': attrs.get('STATUS', 'Unknown'),
                        'distance_km': round(distance_km, 1),
                        'distance_mi': round(km_to_miles(distance_km), 1),
                        'lat': sub_lat,
                        'lon': sub_lon,
                        'direction': direction
                    }
                    substations.append(substation)
        
        # Sort by distance and return
        substations.sort(key=lambda x: x['distance_km'])
        return substations
        
    except Exception as e:
        print(f"Warning: Substation query failed: {e}")
        return []


def query_fiber(lat: float, lon: float) -> Dict[str, Any]:
    """
    Query FCC Broadband Map for fiber availability at coordinates
    Returns fiber availability information
    """
    # FCC Broadband Map API
    url = "https://broadbandmap.fcc.gov/api/public/map/listAvailabilities"
    
    params = {
        'latitude': lat,
        'longitude': lon
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        fiber_info = {
            'has_fiber': False,
            'providers': [],
            'max_download_mbps': 0,
            'max_upload_mbps': 0,
            'technology_types': []
        }
        
        if 'results' in data:
            technologies = set()
            providers = set()
            max_down = 0
            max_up = 0
            has_fiber = False
            
            for result in data['results']:
                tech = result.get('technology', '').lower()
                provider = result.get('provider_name', '')
                down_speed = result.get('max_advertised_download_speed', 0)
                up_speed = result.get('max_advertised_upload_speed', 0)
                
                if 'fiber' in tech or tech in ['50', '70']:  # FCC tech codes for fiber
                    has_fiber = True
                
                technologies.add(tech)
                if provider:
                    providers.add(provider)
                
                max_down = max(max_down, down_speed or 0)
                max_up = max(max_up, up_speed or 0)
            
            fiber_info.update({
                'has_fiber': has_fiber,
                'providers': list(providers),
                'max_download_mbps': max_down,
                'max_upload_mbps': max_up,
                'technology_types': list(technologies)
            })
        
        return fiber_info
        
    except Exception as e:
        print(f"Warning: Fiber query failed: {e}")
        return {
            'has_fiber': False,
            'providers': [],
            'max_download_mbps': 0,
            'max_upload_mbps': 0,
            'technology_types': [],
            'error': str(e)
        }