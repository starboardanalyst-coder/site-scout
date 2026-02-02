#!/usr/bin/env python3
"""
Site Scout — coordinate-based infrastructure lookup for Texas.

Usage:
    python main.py --lat 31.356 --lon -103.163
    python main.py --lat 31.356 --lon -103.163 --radius 50 --format json
"""

import argparse
import sys
from datetime import datetime, timezone

import yaml

from scout.infra import (
    query_pipelines, query_transmission_lines, query_fiber,
    query_substations, query_city_limits_distance,
)
from scout.regulatory import check_city_limits, check_attainment
from scout.formatter import format_markdown, format_json


def load_config():
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {
            "default_radius_km": 50,
            "region": "Texas",
            "pipelines": {"operators": ["Kinder Morgan", "Targa", "El Paso"]},
            "transmission": {"min_voltage_kv": 69},
        }


def main():
    parser = argparse.ArgumentParser(
        description="Site Scout — infrastructure lookup for Texas coordinates"
    )
    parser.add_argument("--lat", type=float, required=True, help="Latitude")
    parser.add_argument("--lon", type=float, required=True, help="Longitude")
    parser.add_argument("--radius", type=float, default=None,
                        help="Search radius in km (default: 50)")
    parser.add_argument("--format", choices=["markdown", "json"],
                        default="markdown", help="Output format")

    args = parser.parse_args()

    if not (-90 <= args.lat <= 90) or not (-180 <= args.lon <= 180):
        print("Error: invalid coordinates", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    radius_km = args.radius or config.get("default_radius_km", 50)
    operators = config.get("pipelines", {}).get("operators", ["Kinder Morgan", "Targa", "El Paso"])
    min_kv = config.get("transmission", {}).get("min_voltage_kv", 69)

    print(f"🔍 Scouting ({args.lat:.4f}, {args.lon:.4f}) — {radius_km}km radius...",
          file=sys.stderr)

    results = {
        "coordinates": {"lat": args.lat, "lon": args.lon},
        "radius_km": radius_km,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipelines": [],
        "transmission_lines": [],
        "substations": [],
        "fiber": {},
        "city_limits": {},
        "nearby_cities": [],
        "attainment": {},
    }

    try:
        print("📡 Querying pipelines...", file=sys.stderr)
        results["pipelines"] = query_pipelines(
            args.lat, args.lon, radius_km,
            operators=operators, include_all=True,
        )

        print("⚡ Querying transmission lines...", file=sys.stderr)
        results["transmission_lines"] = query_transmission_lines(
            args.lat, args.lon, radius_km,
            min_voltage_kv=min_kv,
        )

        print("🏭 Querying substations/power plants...", file=sys.stderr)
        results["substations"] = query_substations(args.lat, args.lon, radius_km)

        print("🌐 Checking fiber...", file=sys.stderr)
        results["fiber"] = query_fiber(args.lat, args.lon)

        print("🏙️ Checking city limits...", file=sys.stderr)
        results["city_limits"] = check_city_limits(args.lat, args.lon)

        print("📏 Querying city limit distances...", file=sys.stderr)
        results["nearby_cities"] = query_city_limits_distance(args.lat, args.lon, radius_km)

        print("🌿 Checking EPA attainment...", file=sys.stderr)
        results["attainment"] = check_attainment(args.lat, args.lon)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        print(format_json(results))
    else:
        print(format_markdown(results))


if __name__ == "__main__":
    main()
