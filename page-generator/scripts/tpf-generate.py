#!/usr/bin/env python3
"""
tpf-generate.py - Generate trip-data.json from structured JSON input.

Usage:
    tpf-generate.py --from-json input.json --output trip-data.json
    cat input.json | tpf-generate.py --from-stdin --pretty

Features:
    - Accept structured JSON from files or stdin
    - Auto-fetch metro data for supported cities
    - Auto-search Wikimedia images for attractions
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Framework paths
SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_DIR = Path(__file__).resolve().parents[2]
METRO_SCRIPT = FRAMEWORK_DIR / "scripts" / "fetch_subway_data.py"
IMAGE_SCRIPT = SCRIPT_DIR / "wikimedia_image_search.py"

def error(msg):
    print(f"[tpf-generate] ❌ {msg}", file=sys.stderr)
    sys.exit(1)

def info(msg):
    print(f"[tpf-generate] ℹ️  {msg}")

def success(msg):
    print(f"[tpf-generate] ✅ {msg}")

def load_input_json(args):
    """Load structured trip input from a file or stdin."""
    if args.from_json:
        try:
            with open(args.from_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            error(f"Input JSON file not found: {args.from_json}")
        except json.JSONDecodeError as exc:
            error(f"Invalid JSON in {args.from_json}: {exc}")

    if args.from_stdin:
        raw = sys.stdin.read().strip()
        if not raw:
            error("No JSON content received from stdin")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            error(f"Invalid JSON from stdin: {exc}")

    error("One of --from-json or --from-stdin is required")

def validate_input_data(data):
    """Validate minimum required structured input."""
    if not isinstance(data, dict):
        error("Input JSON must be an object")

    if not data.get("city"):
        error("Input JSON is missing required field: city")

    days = data.get("days")
    if days is None:
        error("Input JSON is missing required field: days")
    if not isinstance(days, int) or days <= 0:
        error("Field 'days' must be a positive integer")

    nights = data.get("nights")
    if nights is not None and (not isinstance(nights, int) or nights < 0):
        error("Field 'nights' must be a non-negative integer")

def fetch_metro_data(city):
    """Fetch metro data if city is supported."""
    if not METRO_SCRIPT.exists():
        return None

    info(f"Fetching metro data for {city}...")
    try:
        result = subprocess.run(
            ["python3", str(METRO_SCRIPT), city, "--pretty"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        info(f"Metro data fetch timed out after 30s")
    except json.JSONDecodeError as e:
        info(f"Metro data parse failed: {e}")
    except FileNotFoundError:
        info(f"Metro script not found: {METRO_SCRIPT}")
    except subprocess.CalledProcessError as e:
        info(f"Metro data fetch failed: {e}")
    return None

def search_images(query, limit=3):
    """Search Wikimedia Commons for images."""
    if not IMAGE_SCRIPT.exists():
        return None

    info(f"Searching image for: {query}")
    try:
        result = subprocess.run(
            ["python3", str(IMAGE_SCRIPT), query, "--limit", str(limit)],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("thumbUrl") or data[0].get("url")
    except subprocess.TimeoutExpired:
        info(f"Image search timed out after 30s")
    except json.JSONDecodeError as e:
        info(f"Image search parse failed: {e}")
    except FileNotFoundError:
        info(f"Image search script not found: {IMAGE_SCRIPT}")
    except subprocess.CalledProcessError as e:
        info(f"Image search failed: {e}")
    return None

def normalize_side_trip(side_trip):
    """Normalize side trip input to match trip schema and renderer."""
    if isinstance(side_trip, dict):
        required_fields = ("name", "date", "role", "description")
        if all(field in side_trip for field in required_fields):
            normalized = dict(side_trip)
            normalized["name"] = str(normalized.get("name", "")).strip()
            normalized["date"] = str(normalized.get("date", "")).strip()
            normalized["role"] = str(normalized.get("role", "")).strip()
            normalized["description"] = str(normalized.get("description", "")).strip()
            if "image" in normalized and normalized["image"] is not None:
                normalized["image"] = str(normalized["image"]).strip()
            return normalized

        highlights = side_trip.get("highlights", [])
        if isinstance(highlights, list):
            description = "；".join(str(item) for item in highlights if item is not None).strip()
        elif highlights is None:
            description = ""
        else:
            description = str(highlights).strip()

        return {
            "name": str(side_trip.get("destination") or side_trip.get("name") or "").strip(),
            "date": str(side_trip.get("duration") or side_trip.get("date") or "1天").strip(),
            "role": str(side_trip.get("role") or "周边侧游").strip(),
            "description": description or str(
                side_trip.get("description") or "可作为周边顺路行程"
            ).strip(),
            "image": str(side_trip.get("image") or "").strip()
        }

    return {
        "name": str(side_trip).strip(),
        "date": "1天",
        "role": "周边侧游",
        "description": "可作为周边顺路行程",
        "image": ""
    }

def generate_trip_data(parsed, options):
    """Generate complete trip-data.json structure."""
    
    city = parsed.get("city", "目的地")
    days = parsed.get("days", 3)
    nights = parsed.get("nights", days - 1) if parsed.get("nights") else days - 1
    
    # Generate dates (starting from next month 1st for example)
    from datetime import datetime, timedelta
    start_date = datetime.now().replace(day=1) + timedelta(days=32)
    start_date = start_date.replace(day=1)
    
    date_range = f"{start_date.strftime('%Y/%m/%d')} - {(start_date + timedelta(days=days-1)).strftime('%Y/%m/%d')}"
    
    # Build day-by-day itinerary
    days_data = []
    for i in range(days):
        day_date = start_date + timedelta(days=i)
        day_num = i + 1
        
        day_data = {
            "day": f"Day {day_num}",
            "date": day_date.strftime("%m/%d"),
            "theme": f"{city}探索日" if i < days - 1 else "返程日",
            "city": city,
            "hotel": f"{city}酒店" if i < days - 1 else None,
            "metroLines": [],
            "segments": {
                "morning": ["早餐后出发"],
                "afternoon": ["游览主要景点"],
                "evening": ["晚餐及休息"] if i < days - 1 else []
            },
            "note": "根据实际行程调整"
        }
        days_data.append(day_data)
    
    # Build attractions with auto-images if requested
    attractions_data = []
    for attr in parsed.get("attractions", []):
        image_url = None
        if options.get("with_images"):
            image_url = search_images(f"{attr} {city}", limit=1)
        
        attractions_data.append({
            "name": attr,
            "city": city,
            "type": "景点",
            "image": image_url or "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1200&q=80",
            "description": f"{city}著名景点",
            "bestFor": ["观光", "拍照"]
        })
    
    # Metro coverage
    metro_data = None
    if options.get("with_metro"):
        metro_data = fetch_metro_data(city)
    
    metro_lines = []
    if metro_data and "lines" in metro_data:
        for line in metro_data["lines"][:5]:  # Max 5 lines
            metro_lines.append({
                "name": line.get("name", "未知线路"),
                "day": f"Day {min(len(metro_lines)+1, days)}",
                "status": "planned"
            })
    
    hotels_input = parsed.get("hotels") or []
    if hotels_input:
        hotels_data = []
        for hotel in hotels_input:
            if isinstance(hotel, dict):
                hotels_data.append({
                    "phase": hotel.get("phase", "全程"),
                    "name": hotel.get("name", parsed.get("hotel_area") or f"{city}推荐酒店"),
                    "dateRange": hotel.get("dateRange", date_range),
                    "station": hotel.get("station", "市中心"),
                    "status": hotel.get("status", "推荐"),
                    "price": hotel.get("price", "待定"),
                    "distanceToMetro": hotel.get("distanceToMetro", "地铁方便"),
                    "image": hotel.get("image", "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80"),
                    "highlights": hotel.get("highlights", ["位置便利", "交通方便"])
                })
            else:
                hotels_data.append({
                    "phase": "全程",
                    "name": str(hotel),
                    "dateRange": date_range,
                    "station": "市中心",
                    "status": "推荐",
                    "price": "待定",
                    "distanceToMetro": "地铁方便",
                    "image": "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80",
                    "highlights": ["位置便利", "交通方便"]
                })
    else:
        hotels_data = [
            {
                "phase": "全程",
                "name": parsed.get("hotel_area") or f"{city}推荐酒店",
                "dateRange": date_range,
                "station": "市中心",
                "status": "推荐",
                "price": "待定",
                "distanceToMetro": "地铁方便",
                "image": "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80",
                "highlights": ["位置便利", "交通方便"]
            }
        ]

    side_trips_data = []
    for side_trip in parsed.get("side_trips", []):
        normalized_side_trip = normalize_side_trip(side_trip)
        if options.get("with_images") and not normalized_side_trip.get("image"):
            normalized_side_trip["image"] = search_images(f"{normalized_side_trip['name']} 旅游", limit=1) or ""
        side_trips_data.append(normalized_side_trip)

    hero_image = str(parsed.get("heroImage") or "").strip()
    if options.get("with_images") and not hero_image:
        hero_image = search_images(f"{city} 城市风景", limit=1) or ""

    # Build final structure
    trip_data = {
        "meta": {
            "title": f"{city} {days}天{nights}晚旅行计划",
            "subtitle": f"{date_range}｜探索{city}",
            "description": f"{city} {days}天行程规划，包含主要景点和交通安排。"
        },
        "hero": {
            "title": f"{city} {days}天{nights}晚旅行计划",
            "subtitle": f"探索{city}的精彩旅程",
            "dateRange": date_range,
            "tags": [city, f"{days}天{nights}晚"] + parsed.get("attractions", [])[:2],
            "summary": f"这是一份{city} {days}天的旅行计划，涵盖主要景点和实用建议。",
            "heroImage": hero_image
        },
        "stats": [
            {"label": "出发", "value": f"出发地 → {city}"},
            {"label": "返程", "value": f"Day {days} 下午"},
            {"label": "时长", "value": f"{days} 天"},
            {"label": "酒店", "value": parsed.get("hotel_area") or "待定"},
            {"label": "预算", "value": f"约 ¥{parsed.get('budget', '?')}/人" if parsed.get('budget') else "待定"}
        ],
        "hotels": hotels_data,
        "metroCoverage": {
            "goal": "覆盖主要地铁线路，方便出行",
            "lines": metro_lines if metro_lines else []
        },
        "days": days_data,
        "sideTrips": side_trips_data,
        "attractions": attractions_data if attractions_data else [
            {
                "name": f"{city}主要景点",
                "city": city,
                "type": "城市地标",
                "image": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1200&q=80",
                "description": f"{city}代表性景点",
                "bestFor": ["观光", "初访"]
            }
        ],
        "tips": [
            f"提前预订{city}酒店，节假日价格会上涨。",
            "关注天气预报，准备合适的衣物。",
            "下载当地地铁APP，方便查询线路。"
        ]
    }
    
    return trip_data

def main():
    parser = argparse.ArgumentParser(
        prog="tpf-generate",
        description="Generate trip data from structured JSON"
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--from-json", help="Read structured input JSON from file")
    input_group.add_argument("--from-stdin", action="store_true", help="Read structured input JSON from stdin")
    parser.add_argument("--output", "-o", default="trip-data.json", help="Output file")
    parser.add_argument("--with-metro", action="store_true", help="Auto-fetch metro data")
    parser.add_argument("--with-images", action="store_true", help="Auto-search images")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    
    args = parser.parse_args()

    parsed = load_input_json(args)
    validate_input_data(parsed)
    info(f"Loaded input: {json.dumps(parsed, ensure_ascii=False)}")
    
    options = {
        "with_metro": args.with_metro,
        "with_images": args.with_images
    }
    
    trip_data = generate_trip_data(parsed, options)
    
    # Output
    indent = 2 if args.pretty else None
    output = json.dumps(trip_data, ensure_ascii=False, indent=indent)
    
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(output + "\n")
    
    success(f"Generated: {args.output}")
    info(f"City: {trip_data['meta']['title']}")
    info(f"Days: {len(trip_data['days'])}")
    info(f"Attractions: {len(trip_data['attractions'])}")

if __name__ == "__main__":
    main()
