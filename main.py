#!/usr/bin/env python3
"""
Site Scout - Infrastructure lookup tool for Texas
Given GPS coordinates, queries nearby infrastructure and returns a report.
"""

import argparse
import sys
import json
from datetime import datetime
from scout.infra import query_pipelines, query_substations, query_fiber
from scout.regulatory import check_city_limits, check_attainment
from scout.formatter import format_markdown, format_json
import yaml


def load_config():
    """Load configuration from config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        # Default config if file doesn't exist
        return {
            'default_radius_km': 15,
            'region': 'Texas',
            'pipelines': {'operators': ['Kinder Morgan', 'Targa']},
            'substations': {'min_voltage_kv': 69, 'state_filter': 'TX'}
        }


def main():
    parser = argparse.ArgumentParser(
        description='Site Scout - Infrastructure lookup for Texas coordinates'
    )
    parser.add_argument('--lat', type=float, required=True,
                       help='Latitude (decimal degrees)')
    parser.add_argument('--lon', type=float, required=True,
                       help='Longitude (decimal degrees)')
    parser.add_argument('--radius', type=float, default=None,
                       help='Search radius in km (default: from config)')
    parser.add_argument('--format', choices=['markdown', 'json'], 
                       default='markdown', help='Output format')
    
    args = parser.parse_args()
    
    # Validate coordinates
    if not (-90 <= args.lat <= 90):
        print("Error: Latitude must be between -90 and 90", file=sys.stderr)
        sys.exit(1)
    if not (-180 <= args.lon <= 180):
        print("Error: Longitude must be between -180 and 180", file=sys.stderr)
        sys.exit(1)
    
    # Load config
    config = load_config()
    radius_km = args.radius if args.radius else config['default_radius_km']
    
    print(f"🔍 Scouting site at ({args.lat:.4f}, {args.lon:.4f}) within {radius_km}km radius...", 
          file=sys.stderr)
    
    # Gather all data
    results = {
        'coordinates': {'lat': args.lat, 'lon': args.lon},
        'radius_km': radius_km,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'pipelines': [],
        'substations': [],
        'fiber': {},
        'city_limits': {},
        'attainment': {}
    }
    
    try:
        # Infrastructure queries
        print("📡 Querying pipelines...", file=sys.stderr)
        results['pipelines'] = query_pipelines(args.lat, args.lon, radius_km)
        
        print("🏭 Querying substations...", file=sys.stderr)
        results['substations'] = query_substations(args.lat, args.lon, radius_km)
        
        print("🌐 Checking fiber availability...", file=sys.stderr)
        results['fiber'] = query_fiber(args.lat, args.lon)
        
        # Regulatory checks
        print("🏙️ Checking city limits...", file=sys.stderr)
        results['city_limits'] = check_city_limits(args.lat, args.lon)
        
        print("🌿 Checking EPA attainment...", file=sys.stderr)
        results['attainment'] = check_attainment(args.lat, args.lon)
        
    except Exception as e:
        print(f"Error during data collection: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Format output
    if args.format == 'json':
        print(format_json(results))
    else:
        print(format_markdown(results))


if __name__ == '__main__':
    main()