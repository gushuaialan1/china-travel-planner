#!/usr/bin/env python3
"""
search_flyai.py - Search Fliggy/FlyAI for hotel and attraction booking data.

Usage:
    python3 scripts/search_flyai.py --from-json input.json --pretty -o flyai-data.json
    cat input.json | python3 scripts/search_flyai.py --from-stdin --pretty

Returns structured data with booking URLs, images, and prices from Fliggy.
Hotels get detailUrl (booking link) and mainPic (photo).
Attractions get jumpUrl (ticket link), mainPic, and ticketInfo.

Requires: flyai-cli (npm i -g @fly-ai/flyai-cli)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta

SCRIPT_NAME = "search_flyai"


def info(msg):
    print(f"[{SCRIPT_NAME}] ℹ️  {msg}", file=sys.stderr)


def warn(msg):
    print(f"[{SCRIPT_NAME}] ⚠️  {msg}", file=sys.stderr)


def error(msg):
    print(f"[{SCRIPT_NAME}] ❌ {msg}", file=sys.stderr)
    sys.exit(1)


def run_flyai(args_list, timeout=30):
    """Run flyai CLI and return parsed JSON, or None on failure."""
    try:
        result = subprocess.run(
            ["flyai"] + args_list,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            warn(f"flyai returned code {result.returncode}: {result.stderr.strip()[:200]}")
            return None
        return json.loads(result.stdout)
    except FileNotFoundError:
        warn("flyai-cli not found. Install with: npm i -g @fly-ai/flyai-cli")
        return None
    except subprocess.TimeoutExpired:
        warn(f"flyai timed out after {timeout}s")
        return None
    except json.JSONDecodeError as e:
        warn(f"flyai output parse failed: {e}")
        return None


def search_hotels(city, hotel_area=None, check_in=None, check_out=None, max_price=None):
    """Search hotels near a point of interest."""
    args = ["search-hotels", "--dest-name", city]
    if hotel_area:
        args += ["--key-words", hotel_area]
    if check_in:
        args += ["--check-in-date", check_in]
    if check_out:
        args += ["--check-out-date", check_out]
    if max_price:
        args += ["--max-price", str(max_price)]
    args += ["--sort", "rate_desc"]

    info(f"Searching hotels: {city} near {hotel_area or 'city center'}")
    data = run_flyai(args)
    if not data or data.get("status") != 0:
        return []

    hotels = []
    for item in (data.get("data", {}).get("itemList") or []):
        hotels.append({
            "name": item.get("name", ""),
            "price": item.get("price", ""),
            "score": item.get("score", ""),
            "scoreDesc": item.get("scoreDesc", ""),
            "star": item.get("star", ""),
            "address": item.get("address", ""),
            "mainPic": item.get("mainPic", ""),
            "bookingUrl": item.get("detailUrl", ""),
            "interestsPoi": item.get("interestsPoi", ""),
        })
    info(f"Found {len(hotels)} hotels")
    return hotels


def search_attractions(city, attractions):
    """Search each attraction on Fliggy for booking links and images."""
    results = {}
    for name in attractions:
        info(f"Searching attraction: {name}")
        data = run_flyai(["search-poi", "--city-name", city, "--keyword", name])
        if not data or data.get("status") != 0:
            results[name] = {"found": False}
            continue

        items = data.get("data", {}).get("itemList") or []
        # Try to find exact or close match
        match = None
        for item in items:
            item_name = item.get("name", "")
            if name in item_name or item_name in name:
                match = item
                break
        if not match and items:
            match = items[0]  # Best available

        if match:
            ticket_info = match.get("ticketInfo") or {}
            results[name] = {
                "found": True,
                "flyaiName": match.get("name", ""),
                "mainPic": match.get("mainPic", ""),
                "bookingUrl": match.get("jumpUrl", ""),
                "freeStatus": match.get("freePoiStatus", "UNKNOWN"),
                "ticketPrice": ticket_info.get("price"),
                "ticketName": ticket_info.get("ticketName"),
                "address": match.get("address", ""),
                "poiLevel": match.get("poiLevel"),
            }
        else:
            results[name] = {"found": False}

    found_count = sum(1 for v in results.values() if v.get("found"))
    info(f"Found {found_count}/{len(attractions)} attractions on Fliggy")
    return results


def load_input(args):
    """Load input JSON from file or stdin."""
    if args.from_json:
        path = Path(args.from_json).expanduser().resolve()
        if not path.exists():
            error(f"Input file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return json.load(sys.stdin)


def main():
    parser = argparse.ArgumentParser(
        prog=SCRIPT_NAME,
        description="Search Fliggy for hotel and attraction booking data",
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--from-json", help="Input JSON file")
    input_group.add_argument("--from-stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--pretty", action="store_true", help="Pretty print")

    args = parser.parse_args()
    parsed = load_input(args)

    city = parsed.get("city", "")
    if not city:
        error("Missing 'city' in input")

    attractions = parsed.get("attractions", [])
    hotel_area = parsed.get("hotel_area")

    # Compute check-in/out dates
    days = parsed.get("days", 3)
    start = datetime.now().replace(day=1) + timedelta(days=32)
    start = start.replace(day=1)
    check_in = start.strftime("%Y-%m-%d")
    check_out = (start + timedelta(days=days - 1)).strftime("%Y-%m-%d")

    budget = parsed.get("budget")
    max_price_per_night = None
    if budget and days > 0:
        max_price_per_night = int(budget * 0.4 / max(days - 1, 1))  # ~40% of budget on hotel

    output = {
        "city": city,
        "hotels": search_hotels(city, hotel_area, check_in, check_out, max_price_per_night),
        "attractions": search_attractions(city, attractions),
    }

    indent = 2 if args.pretty else None
    text = json.dumps(output, ensure_ascii=False, indent=indent)

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        info(f"Output written to: {out_path}")
    else:
        print(text)


if __name__ == "__main__":
    main()
