# China Travel Planner

An AI-agent skill for planning domestic China trips and generating shareable itinerary web pages.

## How It Works

```
User: "帮我规划清明去长沙玩三天"
  ↓
AI Agent understands intent, searches for real trip plans
  ↓
AI reviews results, writes descriptions, outputs structured JSON
  ↓
tpf toolchain: generate → validate → build → deploy
  ↓
Shareable web page on GitHub Pages
```

**The AI agent is the brain** — it plans the trip, writes content, and ensures quality.
**The toolchain is the hands** — it builds validated, deployable web pages.

## Features

- 🗺️ **Full itinerary pages** with daily schedules, attractions, hotels, metro coverage
- 🏨 **Hotel recommendations** from Fliggy with real prices and booking links (≥3 per trip)
- 🎫 **Attraction booking links** from Fliggy (click to buy tickets)
- 📸 **Real photos** from Fliggy (primary) and Wikimedia Commons (fallback)
- 🚇 **Metro data** auto-fetched for supported cities
- 🔍 **Trip plan search** via Tavily (real itineraries from 小红书, 知乎, etc.)
- ✅ **Schema validation** ensures data integrity
- 🚀 **One-click deploy** to GitHub Pages

## Quick Start

```bash
# Full pipeline (search + generate + validate + build)
python3 scripts/tpf-pipeline.py --from-json input.json --with-metro --pretty

# Or step by step:
python3 scripts/search_travel_info.py --from-json input.json -o data/travel-info.json
python3 scripts/search_flyai.py --from-json input.json -o data/flyai-data.json
# → AI agent reviews travel-info.json, writes descriptions back
python3 page-generator/scripts/tpf-generate.py --from-json input.json --with-metro --pretty -o data/trip-data.json
python3 page-generator/scripts/tpf-cli.py validate
python3 page-generator/scripts/tpf-cli.py build
```

## Input Format

The AI agent produces this JSON:

```json
{
  "city": "长沙",
  "days": 3,
  "nights": 2,
  "attractions": ["岳麓山", "橘子洲", "天心阁"],
  "hotel_area": "五一广场",
  "budget": 2000,
  "hotels": [{"name": "五一广场精选酒店", "station": "五一广场", "price": "约300元/晚"}],
  "side_trips": [{"destination": "岳阳", "duration": "1天", "highlights": ["岳阳楼"]}]
}
```

## Project Structure

```
scripts/
├── tpf-pipeline.py              # One-click pipeline (search → generate → validate → build)
├── search_travel_info.py        # Tavily search for real trip plans
├── search_flyai.py              # Fliggy search for hotels & attractions (booking links + images)
├── fetch_subway_data.py         # Metro data from AMap
├── metro_hotel_match.py         # Hotel-to-metro matching
└── coverage_plan_notes.py       # Metro coverage planning

page-generator/
├── scripts/
│   ├── tpf-generate.py          # Generate trip-data.json from structured input
│   ├── tpf-cli.py               # Validate / Build / Deploy
│   └── wikimedia_image_search.py # Wikimedia image search (fallback)
├── templates/
│   ├── trip-page-tailwind.html   # HTML template
│   ├── trip-renderer.js          # Client-side renderer
│   └── themes/light.js           # Theme definition
└── schema/
    └── trip-schema.json          # JSON Schema for validation

examples/changsha-3day/           # Example input + docs
tests/test_pipeline.py            # Automated tests (6 cases)
SKILL.md                          # AI agent instructions
```

## Image & Booking Priority

| Source | Images | Booking Links | When Used |
|--------|--------|---------------|-----------|
| Fliggy | ✅ Hotel photos, attraction photos | ✅ Hotel booking, ticket purchase | Primary |
| Wikimedia | ✅ CC-licensed photos | ❌ | Fallback when Fliggy has no image |
| Unsplash | ✅ Placeholder | ❌ | Last resort |

## Requirements

- Python 3.10+
- `flyai-cli` (optional): `npm i -g @fly-ai/flyai-cli` — for Fliggy hotel/attraction data
- `TAVILY_API_KEY` (optional): for trip plan search — free tier: 1000 calls/month

## Live Demo

- [长沙 7天6晚行程](https://gushuaialan1.github.io/china-travel-planner/changsha-7day/)
- [目录页](https://gushuaialan1.github.io/china-travel-planner/)

## License

MIT
