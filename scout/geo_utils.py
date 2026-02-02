"""
Geographic utilities for distance calculations and spatial operations
"""

import math
from typing import List


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth
    Returns distance in kilometers
    """
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of Earth in kilometers
    R = 6371.0
    
    return R * c


def km_to_miles(km: float) -> float:
    """Convert kilometers to miles"""
    return km * 0.621371


def miles_to_km(miles: float) -> float:
    """Convert miles to kilometers"""
    return miles / 0.621371


def compass_direction(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> str:
    """
    Calculate the compass direction from one point to another
    Returns direction as string: N, NE, E, SE, S, SW, W, NW
    """
    # Convert to radians
    from_lat, from_lon, to_lat, to_lon = map(math.radians, [from_lat, from_lon, to_lat, to_lon])
    
    # Calculate bearing
    dlon = to_lon - from_lon
    y = math.sin(dlon) * math.cos(to_lat)
    x = (math.cos(from_lat) * math.sin(to_lat) - 
         math.sin(from_lat) * math.cos(to_lat) * math.cos(dlon))
    
    # Get bearing in radians and convert to degrees
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    
    # Normalize to 0-360 degrees
    bearing = (bearing + 360) % 360
    
    # Convert to compass direction
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = round(bearing / 45) % 8
    
    return directions[index]


def create_bbox_from_point(lat: float, lon: float, radius_km: float) -> List[float]:
    """
    Create a bounding box around a point with given radius
    Returns [west, south, east, north] in decimal degrees
    """
    # Approximate conversion from km to degrees
    # 1 degree of latitude ≈ 111 km
    # 1 degree of longitude varies by latitude: ≈ 111 * cos(lat) km
    
    lat_offset = radius_km / 111.0
    lon_offset = radius_km / (111.0 * math.cos(math.radians(lat)))
    
    west = lon - lon_offset
    east = lon + lon_offset
    south = lat - lat_offset
    north = lat + lat_offset
    
    return [west, south, east, north]


def point_in_bbox(lat: float, lon: float, bbox: List[float]) -> bool:
    """
    Check if a point is within a bounding box
    bbox format: [west, south, east, north]
    """
    west, south, east, north = bbox
    return west <= lon <= east and south <= lat <= north


def degrees_to_dms(decimal_degrees: float, is_longitude: bool = False) -> str:
    """
    Convert decimal degrees to degrees, minutes, seconds format
    Returns formatted string like "31°54'00"N" or "102°18'00"W"
    """
    abs_dd = abs(decimal_degrees)
    degrees = int(abs_dd)
    minutes_float = (abs_dd - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    
    if is_longitude:
        direction = "E" if decimal_degrees >= 0 else "W"
    else:
        direction = "N" if decimal_degrees >= 0 else "S"
    
    return f'{degrees}°{minutes:02d}\'{seconds:04.1f}"{direction}'


def format_coordinates(lat: float, lon: float) -> str:
    """
    Format coordinates as DMS string
    """
    lat_dms = degrees_to_dms(lat, is_longitude=False)
    lon_dms = degrees_to_dms(lon, is_longitude=True)
    return f"{lat_dms}, {lon_dms}"


def calculate_area_km2(bbox: List[float]) -> float:
    """
    Approximate area calculation for a bounding box in km²
    bbox format: [west, south, east, north]
    """
    west, south, east, north = bbox
    
    # Use haversine for more accurate calculation
    # Calculate distances for each side
    width_km = haversine_distance(south, west, south, east)
    height_km = haversine_distance(south, west, north, west)
    
    return width_km * height_km