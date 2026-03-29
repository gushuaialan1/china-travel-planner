---
name: china-travel-planner
description: Generate shareable travel itinerary web pages for domestic China trips. This skill is for AI agents — the agent handles trip planning and the toolchain handles page generation, validation, and deployment. Use when the user wants a travel plan, itinerary page, or asks for help planning a trip within China.
---

# China Travel Planner

An AI-agent skill for planning domestic China trips and generating shareable itinerary web pages.

**Architecture**: The AI agent is the brain — it understands user intent, picks destinations, plans daily itineraries, and produces structured data. The `tpf` toolchain is the hands — it validates data, builds HTML pages, and deploys them.

## Quick Start

```bash
# 1. Agent prepares input JSON (see Input Format below)
# 2. Run the pipeline
python3 scripts/tpf-pipeline.py --from-json input.json --with-metro --with-images --pretty

# Or step by step:
python3 scripts/search_travel_info.py --from-json input.json --pretty -o search-results.json
python3 page-generator/scripts/tpf-generate.py --from-json input.json --with-metro --with-images --pretty -o trip-data.json
python3 page-generator/scripts/tpf-cli.py validate
python3 page-generator/scripts/tpf-cli.py build
python3 page-generator/scripts/tpf-cli.py deploy --to gh-pages
```

## End-to-End Flow

```
User: "帮我规划清明去长沙玩三天"
  ↓
Step 1: AI Agent understands intent, plans itinerary
  ↓
Step 2: search_travel_info.py searches real travel guides (Tavily)
  ↓
Step 3: AI enriches plan with search results (opening hours, tips, routes)
  ↓
Step 4: AI outputs structured input JSON
  ↓
Step 5: tpf-generate.py → trip-data.json (schema-compliant skeleton)
  ↓
Step 6: tpf validate → checks against trip-schema.json
  ↓
Step 7: tpf build → dist/index.html
  ↓
Step 8: tpf deploy → GitHub Pages (optional)
```

## Input Format

The agent produces this JSON. Minimum required fields: `city` and `days`.

```json
{
  "city": "长沙",
  "days": 3,
  "nights": 2,
  "attractions": ["岳麓山", "橘子洲", "天心阁", "太平街", "湖南省博物馆"],
  "hotel_area": "五一广场",
  "budget": 2000,
  "hotels": [
    {
      "name": "五一广场精选酒店",
      "station": "五一广场",
      "price": "约300元/晚",
      "highlights": ["地铁1/2号线换乘", "步行至太平街5分钟"]
    }
  ],
  "side_trips": ["韶山", "橘子洲烟花"]
}
```

## Tools Reference

### `scripts/tpf-pipeline.py` — One-click pipeline

Runs the full flow: search → generate → validate → build → (optional) deploy.

```bash
python3 scripts/tpf-pipeline.py --from-json input.json --with-metro --pretty
python3 scripts/tpf-pipeline.py --from-stdin --skip-search --deploy
```

Options:
| Flag | Description |
|------|-------------|
| `--from-json FILE` | Read input from JSON file |
| `--from-stdin` | Read input from stdin |
| `--output-dir DIR` | Output directory (default: current) |
| `--skip-search` | Skip Tavily search step |
| `--skip-validate` | Skip schema validation |
| `--with-metro` | Auto-fetch metro data |
| `--with-images` | Auto-search Wikimedia images |
| `--pretty` | Pretty-print JSON |
| `--deploy` | Deploy to GitHub Pages after build |

### `scripts/search_travel_info.py` — Search travel guides

Searches Tavily for each attraction and returns structured guide data (opening hours, tickets, tips, routes).

```bash
python3 scripts/search_travel_info.py --city 长沙 --attractions 岳麓山 橘子洲 天心阁 --pretty
echo '{"city":"长沙","attractions":["岳麓山"]}' | python3 scripts/search_travel_info.py --from-stdin --pretty
```

Requires: `TAVILY_API_KEY` environment variable (free tier: 1000 calls/month).

Output:
```json
{
  "city": "长沙",
  "results": {
    "岳麓山": {
      "summary": "开放6:00-22:00，需预约。岳麓书院门票40元。",
      "sources": [{"title": "...", "url": "...", "content": "...", "score": 0.99}]
    }
  }
}
```

### `page-generator/scripts/tpf-generate.py` — Generate trip-data.json

Converts structured input JSON into a schema-compliant `trip-data.json` skeleton.

```bash
python3 page-generator/scripts/tpf-generate.py --from-json input.json --pretty -o trip-data.json
cat input.json | python3 page-generator/scripts/tpf-generate.py --from-stdin --with-metro --with-images -o trip-data.json
```

### `page-generator/scripts/tpf-cli.py` — Validate, Build, Deploy

```bash
python3 page-generator/scripts/tpf-cli.py validate        # Check trip-data.json against schema
python3 page-generator/scripts/tpf-cli.py build            # Build dist/index.html
python3 page-generator/scripts/tpf-cli.py deploy --to gh-pages  # Deploy to GitHub Pages
```

### `scripts/fetch_subway_data.py` — Metro data

Fetches metro line and station data from AMap for a given city.

```bash
python3 scripts/fetch_subway_data.py 长沙 --pretty
```

### `scripts/metro_hotel_match.py` — Hotel-metro matching

Ranks hotels by proximity to target metro stations.

```bash
python3 scripts/metro_hotel_match.py --subway data.json --hotels hotels.json --target-station 黄土岭 --pretty
```

### `page-generator/scripts/wikimedia_image_search.py` — Free images

Searches Wikimedia Commons for attraction images (CC/Public Domain).

```bash
python3 page-generator/scripts/wikimedia_image_search.py "橘子洲 长沙" --limit 3 --pretty
```

## Planning Guidelines for the AI Agent

### What the agent should do

1. **Understand the request**: Extract city, dates, duration, budget, traveler type, must-visit places, constraints.
2. **Make assumptions when info is missing**: Don't block on questions. State assumptions and give a draft plan. Only ask if critical info (destination) is truly unknown.
3. **Search for real data**: Use `search_travel_info.py` to get opening hours, ticket prices, recommended routes, crowd tips.
4. **Plan daily itineraries**: Assign attractions to days with morning/afternoon/evening segments. Consider geography (group nearby places).
5. **Pick hotels**: Recommend areas near metro interchanges or central locations.
6. **Output structured JSON**: Follow the Input Format above.

### Planning heuristics

- **Weekend/short break** (2-3 days): Keep it compact, one area, avoid over-scheduling.
- **Family trip**: Fewer hotel changes, no aggressive early departures, kid-friendly attractions.
- **Holiday trip**: Warn about crowds, suggest early/late windows, offer crowd-avoidance alternatives.
- **Budget trip**: Prefer rail over flight, central hotels over scenic isolation.
- **Metro coverage trip**: Use `fetch_subway_data.py` and `coverage_plan_notes.py` for line-riding plans.

### Content quality

When filling `trip-data.json`, write content that is:
- **Specific**: "岳麓书院门票40元，建议游览2小时" not "著名景点，值得一去"
- **Actionable**: Include opening hours, ticket prices, transport from hotel
- **Honest**: Mention crowds, queues, seasonal closures
- **Concise**: Card text should be scannable, not essays

## Schema

Full JSON schema: `page-generator/schema/trip-schema.json`

Required top-level keys: `meta`, `hero`, `stats`, `hotels`, `metroCoverage`, `days`, `sideTrips`, `attractions`, `tips`

Key structures:
- `days[].segments`: `{morning: [...], afternoon: [...], evening: [...]}` — each is an array of activity strings
- `attractions[]`: `{name, city, type, description, bestFor[], image}`
- `hotels[]`: `{phase, name, dateRange, station, status, price, distanceToMetro, image, highlights[]}`

## Examples

See `examples/changsha-3day/` for a complete end-to-end example with input.json and README.

## References

Read these only when needed:
- `references/subway-aware-planning.md` — Metro-line coverage planning
- `references/domestic-planning-prompts.md` — Common trip phrasing patterns
- `references/structured-output-mode.md` — Structured + readable dual output
- `page-generator/schema/trip-content-guidelines.md` — Content writing guide
