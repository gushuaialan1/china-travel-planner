#!/usr/bin/env python3
"""
search_travel_info.py - Search attraction travel tips with the Tavily Search API.

Usage:
    search_travel_info.py --from-json input.json --pretty
    cat input.json | search_travel_info.py --from-stdin --output result.json
    search_travel_info.py --city 长沙 --attractions 岳麓山 橘子洲 天心阁

Features:
    - Accept city + attractions from JSON file, stdin, or CLI args
    - Query Tavily Search once per attraction
    - Return structured JSON summaries and source snippets
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib import error, request


SCRIPT_NAME = "search_travel_info"
DEFAULT_QUERY_TEMPLATE = "{city} {attraction} 行程规划 几日游 路线安排 攻略"
TAVILY_API_URL = "https://api.tavily.com/search"
TAVILY_TIMEOUT_SECONDS = 10
PREFERRED_CHINESE_DOMAINS = [
    "bendibao.com",
    "ctrip.com",
    "mafengwo.cn",
    "dianping.com",
    "baidu.com",
    "zhihu.com",
    "xiaohongshu.com",
    "sohu.com",
    "163.com",
]


def error_exit(msg: str) -> None:
    print(f"[{SCRIPT_NAME}] ❌ {msg}", file=sys.stderr)
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"[{SCRIPT_NAME}] ⚠️  {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"[{SCRIPT_NAME}] ℹ️  {msg}", file=sys.stderr)


def load_input_json(args: argparse.Namespace) -> Dict[str, Any]:
    """Load input JSON from a file or stdin."""
    if args.from_json:
        try:
            with open(args.from_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            error_exit(f"Input JSON file not found: {args.from_json}")
        except json.JSONDecodeError as exc:
            error_exit(f"Invalid JSON in {args.from_json}: {exc}")

    if args.from_stdin:
        raw = sys.stdin.read().strip()
        if not raw:
            error_exit("No JSON content received from stdin")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            error_exit(f"Invalid JSON from stdin: {exc}")

    error_exit("One of --from-json, --from-stdin, or --city/--attractions is required")


def build_input_data(args: argparse.Namespace) -> Dict[str, Any]:
    """Build a normalized input payload from CLI or JSON input."""
    if args.city or args.attractions:
        if not args.city:
            error_exit("--city is required when using --attractions")
        if not args.attractions:
            error_exit("--attractions is required when using --city")
        return {
            "city": args.city,
            "attractions": args.attractions,
        }

    return load_input_json(args)


def validate_input_data(data: Dict[str, Any]) -> None:
    """Validate the minimum required input structure."""
    if not isinstance(data, dict):
        error_exit("Input JSON must be an object")

    city = data.get("city")
    attractions = data.get("attractions")

    if not isinstance(city, str) or not city.strip():
        error_exit("Field 'city' is required and must be a non-empty string")

    if not isinstance(attractions, list) or not attractions:
        error_exit("Field 'attractions' is required and must be a non-empty array")

    for index, attraction in enumerate(attractions, start=1):
        if not isinstance(attraction, str) or not attraction.strip():
            error_exit(f"Field 'attractions[{index - 1}]' must be a non-empty string")


def build_query(city: str, attraction: str, query_template: str) -> str:
    """Render a query string for Tavily search."""
    try:
        return query_template.format(city=city, attraction=attraction)
    except KeyError as exc:
        error_exit(f"Invalid --query-template placeholder: {exc}")
        raise


def search_attraction(api_key: str, query: str) -> Dict[str, Any]:
    """Call Tavily Search API and return the parsed JSON payload."""
    payload = json.dumps(
        {
            "api_key": api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": 3,
            "include_answer": True,
        }
    ).encode("utf-8")

    req = request.Request(
        TAVILY_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    with request.urlopen(req, timeout=TAVILY_TIMEOUT_SECONDS) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def normalize_result(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Tavily result item into the output source schema."""
    return {
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "content": item.get("content", ""),
        "score": item.get("score"),
    }


def collect_travel_info(city: str, attractions: List[str], api_key: str, query_template: str) -> Dict[str, Any]:
    """Search travel info for each attraction and keep partial success on failures."""
    results: Dict[str, Any] = {}

    for attraction in attractions:
        query = build_query(city, attraction, query_template)
        info(f"Searching: {query}")
        try:
            payload = search_attraction(api_key, query)
            sources = [normalize_result(item) for item in payload.get("results", [])]
            results[attraction] = {
                "summary": payload.get("answer", "") or "",
                "sources": sources,
            }
        except error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc)
            warn(f"Search failed for {attraction}: HTTP {exc.code} {detail}")
        except error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            warn(f"Search failed for {attraction}: {reason}")
        except json.JSONDecodeError as exc:
            warn(f"Search failed for {attraction}: invalid JSON response ({exc})")
        except Exception as exc:
            warn(f"Search failed for {attraction}: {exc}")

    return {
        "city": city,
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    """Build CLI arguments."""
    parser = argparse.ArgumentParser(
        prog=SCRIPT_NAME,
        description="Search attraction travel guide information from Tavily and output structured JSON.",
    )

    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--from-json", help="Read input JSON from file")
    input_group.add_argument("--from-stdin", action="store_true", help="Read input JSON from stdin")

    parser.add_argument("--city", help="City name, used with --attractions")
    parser.add_argument("--attractions", nargs="+", help="One or more attraction names")
    parser.add_argument(
        "--query-template",
        default=DEFAULT_QUERY_TEMPLATE,
        help="Custom Tavily query template. Available placeholders: {city}, {attraction}",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON output")
    parser.add_argument("--output", "-o", help="Write JSON output to file")

    args = parser.parse_args()

    if not (args.from_json or args.from_stdin or args.city or args.attractions):
        parser.error("one input mode is required: --from-json, --from-stdin, or --city with --attractions")

    if bool(args.city) != bool(args.attractions):
        parser.error("--city and --attractions must be used together")

    return args


def main() -> None:
    """CLI entry point."""
    args = parse_args()

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        error_exit("TAVILY_API_KEY environment variable is not set")

    data = build_input_data(args)
    validate_input_data(data)

    city = data["city"].strip()
    attractions = [item.strip() for item in data["attractions"]]
    info(f"Loaded input for city={city}, attractions={len(attractions)}")

    output_data = collect_travel_info(
        city=city,
        attractions=attractions,
        api_key=api_key,
        query_template=args.query_template,
    )

    output_text = json.dumps(output_data, ensure_ascii=False, indent=2 if args.pretty else None)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output_text + "\n", encoding="utf-8")
        info(f"Wrote output: {output_path}")

    print(output_text)


if __name__ == "__main__":
    main()
