"""
Regulatory checks for city limits and EPA attainment status
"""

import requests
import json
import os
from typing import Dict, Any, List


# Cache directory
CACHE_DIR = "cache"
EPA_NONATTAINMENT_CACHE = os.path.join(CACHE_DIR, "epa_nonattainment.json")


def ensure_cache_dir():
    """Create cache directory if it doesn't exist"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def check_city_limits(lat: float, lon: float) -> Dict[str, Any]:
    """
    Check if coordinates fall within incorporated city limits
    Uses US Census Bureau geocoder API
    """
    url = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    
    params = {
        'x': lon,
        'y': lat,
        'benchmark': 'Public_AR_Current',
        'vintage': 'Current_Current',
        'format': 'json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        result = {
            'in_city': False,
            'city_name': None,
            'county': None,
            'state': None
        }
        
        if 'result' in data and 'geographies' in data['result']:
            geographies = data['result']['geographies']
            
            # Check for incorporated places
            if 'Incorporated Places' in geographies:
                places = geographies['Incorporated Places']
                if places:
                    place = places[0]  # Take the first match
                    result.update({
                        'in_city': True,
                        'city_name': place.get('NAME'),
                        'state': place.get('STATE')
                    })
            
            # Get county information
            if 'Counties' in geographies:
                counties = geographies['Counties']
                if counties:
                    county = counties[0]
                    result['county'] = county.get('NAME')
                    result['county_fips'] = f"{county.get('STATE','')}{county.get('COUNTY','')}"
                    if not result['state']:
                        result['state'] = county.get('STATE')

            # Get census tract
            if 'Census Tracts' in geographies:
                tracts = geographies['Census Tracts']
                if tracts:
                    result['census_tract'] = tracts[0].get('TRACT')
        
        return result
        
    except Exception as e:
        print(f"Warning: City limits check failed: {e}")
        return {
            'in_city': False,
            'city_name': None,
            'county': None,
            'state': None,
            'error': str(e)
        }


def load_epa_nonattainment_data() -> Dict[str, List[str]]:
    """
    Load EPA nonattainment areas data from cache or download if not available
    Returns dict mapping county FIPS codes to list of nonattainment pollutants
    """
    ensure_cache_dir()
    
    # Check if we have cached data
    if os.path.exists(EPA_NONATTAINMENT_CACHE):
        try:
            with open(EPA_NONATTAINMENT_CACHE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load cached EPA data: {e}")
    
    # If no cache or cache failed, create minimal Texas nonattainment data
    # This is a simplified version - in production you'd download the full EPA dataset
    texas_nonattainment = {
        # Harris County (Houston area) - Ozone nonattainment
        "48201": ["Ozone"],
        # Dallas County - Ozone nonattainment
        "48113": ["Ozone"],
        # Tarrant County (Fort Worth) - Ozone nonattainment  
        "48439": ["Ozone"],
        # Collin County - Ozone nonattainment
        "48085": ["Ozone"],
        # Denton County - Ozone nonattainment
        "48121": ["Ozone"],
        # El Paso County - Ozone nonattainment
        "48141": ["Ozone"]
    }
    
    try:
        with open(EPA_NONATTAINMENT_CACHE, 'w') as f:
            json.dump(texas_nonattainment, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not cache EPA data: {e}")
    
    return texas_nonattainment


def get_county_fips(lat: float, lon: float) -> str:
    """
    Get the county FIPS code for given coordinates
    """
    url = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    
    params = {
        'x': lon,
        'y': lat,
        'benchmark': 'Public_AR_Current',
        'vintage': 'Current_Current',
        'format': 'json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if ('result' in data and 'geographies' in data['result'] 
            and 'Counties' in data['result']['geographies']):
            counties = data['result']['geographies']['Counties']
            if counties:
                county = counties[0]
                state_fips = county.get('STATE')
                county_fips = county.get('COUNTY')
                if state_fips and county_fips:
                    return f"{state_fips}{county_fips}"
        
        return None
        
    except Exception as e:
        print(f"Warning: County FIPS lookup failed: {e}")
        return None


def check_attainment(lat: float, lon: float) -> Dict[str, Any]:
    """
    Check EPA attainment status for coordinates
    Returns attainment status and any nonattainment pollutants
    """
    try:
        # First get county FIPS code
        county_fips = get_county_fips(lat, lon)
        
        if not county_fips:
            return {
                'attainment': True,  # Default to attainment if lookup fails
                'county': 'Unknown County',
                'pollutants_nonattainment': [],
                'error': 'Could not determine county'
            }
        
        # Get city limits info for county name
        city_info = check_city_limits(lat, lon)
        county_name = city_info.get('county', 'Unknown County')
        
        # Load nonattainment data
        nonattainment_data = load_epa_nonattainment_data()
        
        # Check if county is in nonattainment
        pollutants = nonattainment_data.get(county_fips, [])
        
        return {
            'attainment': len(pollutants) == 0,
            'county': f"{county_name}, TX" if county_name else "Unknown County, TX",
            'pollutants_nonattainment': pollutants,
            'county_fips': county_fips
        }
        
    except Exception as e:
        print(f"Warning: Attainment check failed: {e}")
        return {
            'attainment': True,  # Default to attainment on error
            'county': 'Unknown County, TX',
            'pollutants_nonattainment': [],
            'error': str(e)
        }