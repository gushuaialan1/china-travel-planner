#!/usr/bin/env python3
"""
tpf-generate.py - AI-powered trip generation for travel-page-framework.

Usage:
    tpf generate "杭州3天2晚，西湖+灵隐寺，住湖滨，预算2000"
    tpf generate --from-file prompt.txt --output trip-data.json
    tpf generate "长沙7天地铁全覆盖+湘潭株洲岳阳" --with-metro --with-images

Features:
    - Natural language to structured JSON
    - Auto-fetch metro data for supported cities
    - Auto-search Wikimedia images for attractions
"""

import argparse
import json
import os
import re
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

def parse_number_token(token):
    """Parse Arabic digits, Chinese numerals, and common English number words."""
    if not token:
        return None

    token = token.strip().lower()
    if token.isdigit():
        return int(token)

    english_numbers = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
    }
    if token in english_numbers:
        return english_numbers[token]

    chinese_digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }

    if token in chinese_digits:
        return chinese_digits[token]

    if all(char in "零〇一二两三四五六七八九十百" for char in token):
        total = 0
        current = 0
        for char in token:
            if char in chinese_digits:
                current = chinese_digits[char]
            elif char == "十":
                total += (current or 1) * 10
                current = 0
            elif char == "百":
                total += (current or 1) * 100
                current = 0
        return total + current

    return None

def parse_prompt(prompt):
    """Extract key info from natural language prompt."""
    info(f"Parsing: {prompt}")
    
    result = {
        "city": None,
        "days": None,
        "nights": None,
        "attractions": [],
        "hotel_area": None,
        "budget": None,
        "side_trips": []
    }

    chinese_number_pattern = r'(\d+|[零〇一二两三四五六七八九十百]+)'
    chinese_number_token_pattern = r'(?:\d+|[零〇一二两三四五六七八九十百]+)'
    english_number_pattern = r'(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)'
    english_number_token_pattern = r'(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)'

    city_patterns = [
        rf'(?:去|到|飞|前往|想去|准备去)\s*([\u4e00-\u9fa5]{{2,12}}?)(?=\s*(?:玩|旅游|旅行|逛|待|住|{chinese_number_token_pattern}\s*(?:天|日|晚)|[，,。！？\s]|$))',
        rf'^([\u4e00-\u9fa5]{{2,12}}?)(?=\s*{chinese_number_token_pattern}\s*(?:天|日|晚))',
        rf'(?:go\s+to|visit|travel\s+to|trip\s+to)\s+([A-Za-z][A-Za-z\s-]{{1,40}}?)(?=\s+(?:for\s+)?{english_number_token_pattern}\s+(?:days?|nights?)\b|\s*[,.]|$)',
        rf'\bin\s+([A-Za-z][A-Za-z\s-]{{1,40}}?)(?=\s+(?:for\s+)?{english_number_token_pattern}\s+(?:days?|nights?)\b|\s*[,.]|$)',
        rf'^([A-Za-z][A-Za-z\s-]{{1,40}}?)(?=\s+(?:for\s+)?{english_number_token_pattern}\s+days?\b)',
    ]
    for pattern in city_patterns:
        city_match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if city_match:
            result["city"] = city_match.group(1).strip(" ,，。")
            break

    # Extract days/nights
    days_match = re.search(rf'{chinese_number_pattern}\s*(?:天|日)', prompt)
    if days_match:
        result["days"] = parse_number_token(days_match.group(1))
    else:
        days_match = re.search(rf'{english_number_pattern}\s+days?\b', prompt, flags=re.IGNORECASE)
        if days_match:
            result["days"] = parse_number_token(days_match.group(1))

    nights_match = re.search(rf'{chinese_number_pattern}\s*晚', prompt)
    if nights_match:
        result["nights"] = parse_number_token(nights_match.group(1))
    else:
        nights_match = re.search(rf'{english_number_pattern}\s+nights?\b', prompt, flags=re.IGNORECASE)
        if nights_match:
            result["nights"] = parse_number_token(nights_match.group(1))

    # Extract budget
    budget_patterns = [
        r'预算\s*(?:约|大概|大约|在)?\s*[¥￥]?\s*(\d+)',
        r'(?:budget|under|around)\s*(?:is\s*)?(?:cny|rmb|usd|\$|¥)?\s*(\d+)',
        r'[¥￥$]\s*(\d+)'
    ]
    for pattern in budget_patterns:
        budget_match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if budget_match:
            result["budget"] = int(budget_match.group(1))
            break
    
    # Extract attractions - enhanced patterns
    attractions = []

    # Pattern 1: "去/玩/游览 A、B、C" or "包括 A+B+C"
    attr_match = re.search(r'(?:去|玩|游览|逛|打卡|包括|想去)\s*[:：]?\s*([^预算住，。]+?)(?:等|以及|和|与|，|。|$)', prompt)
    if attr_match:
        parts = re.split(r'[+、/,]', attr_match.group(1))
        for part in parts:
            part = part.strip()
            if part and len(part) >= 2 and not re.match(r'^(预算|住|酒店|\d)', part):
                attractions.append(part)

    # Pattern 2: "景点：A、B、C"
    if not attractions:
        attr_match = re.search(r'景点[:：]\s*([^，。]+)', prompt)
        if attr_match:
            parts = re.split(r'[+、/,]', attr_match.group(1))
            for part in parts:
                part = part.strip()
                if part and len(part) >= 2:
                    attractions.append(part)

    # Pattern 3: Fallback to comma-separated after city/days
    if not attractions:
        # Look for attractions after "N天" or city
        attr_text = re.search(r'(?:天|晚|玩)\s*[:，,]?\s*([^预算住，。]{2,20}(?:[+、][^预算住，。]+)*)', prompt)
        if attr_text:
            parts = re.split(r'[+、/,]', attr_text.group(1))
            for part in parts:
                part = part.strip()
                if part and len(part) >= 2 and not re.match(r'^(预算|住|酒店|\d)', part):
                    attractions.append(part)

    # Remove duplicates while preserving order
    seen = set()
    result["attractions"] = [a for a in attractions if not (a in seen or seen.add(a))]

    # Extract hotel area - enhanced patterns
    hotel_patterns = [
        r'住\s*在?\s*([^，。,]+?)(?:附近|旁边|周边|，|。|$)',
        r'住\s*([^，。,]{2,15}?)(?:酒店|宾馆|民宿)?(?:，|。|$)',
        r'酒店.*?在\s*([^，。,]+)',
        r'(?:住|酒店).*?([^，。]{2,10})(?:附近|片区|区域)',
    ]
    for pattern in hotel_patterns:
        hotel_match = re.search(pattern, prompt)
        if hotel_match:
            hotel_area = hotel_match.group(1).strip(" ,，。附近旁边")
            if hotel_area and len(hotel_area) >= 2:
                result["hotel_area"] = hotel_area
                break

    # Extract side trips - enhanced patterns
    side_patterns = [
        r'(?:加上?|以及|和|连带|顺路|连同)\s*([^，。]{2,8})(?:方向|顺路|一起|一日游)?',
        r'周边[城市]?[:：]?\s*([^，。]+)',
        r'(?: cover|visit)\s+[^+]+[+\/]([^，。,]+)',
    ]
    for pattern in side_patterns:
        side_match = re.search(pattern, prompt)
        if side_match:
            cities = re.split(r'[、/+，,]', side_match.group(1))
            side_trips = [c.strip() for c in cities if len(c.strip()) >= 2]
            if side_trips:
                result["side_trips"] = side_trips
                break
    
    return result

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
            "heroImage": ""
        },
        "stats": [
            {"label": "出发", "value": f"出发地 → {city}"},
            {"label": "返程", "value": f"Day {days} 下午"},
            {"label": "时长", "value": f"{days} 天"},
            {"label": "酒店", "value": parsed.get("hotel_area") or "待定"},
            {"label": "预算", "value": f"约 ¥{parsed.get('budget', '?')}/人" if parsed.get('budget') else "待定"}
        ],
        "hotels": [
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
        ],
        "metroCoverage": {
            "goal": "覆盖主要地铁线路，方便出行",
            "lines": metro_lines if metro_lines else []
        },
        "days": days_data,
        "sideTrips": [],
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
        description="Generate trip data from natural language"
    )
    parser.add_argument("prompt", nargs="?", help="Natural language description of the trip")
    parser.add_argument("--from-file", "-f", help="Read prompt from file")
    parser.add_argument("--output", "-o", default="trip-data.json", help="Output file")
    parser.add_argument("--with-metro", action="store_true", help="Auto-fetch metro data")
    parser.add_argument("--with-images", action="store_true", help="Auto-search images")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    
    args = parser.parse_args()
    
    # Get prompt
    if args.from_file:
        with open(args.from_file, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.print_help()
        sys.exit(1)
    
    # Parse and generate
    parsed = parse_prompt(prompt)
    info(f"Parsed: {json.dumps(parsed, ensure_ascii=False)}")
    
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
