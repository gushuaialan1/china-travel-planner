# china-travel-planner

An [OpenClaw](https://github.com/openclaw/openclaw) skill for AI agents to plan domestic China trips and generate shareable itinerary web pages.

## Architecture

The AI agent is the brain — it understands user intent, picks destinations, plans daily itineraries, and produces structured data. The `tpf` toolchain is the hands — it validates data, builds HTML pages, and deploys them.

```
User request → AI Agent plans itinerary → Structured JSON
  → tpf-generate (scaffold) → tpf validate → tpf build → HTML page
  → tpf deploy → GitHub Pages
```

## Quick Start

```bash
# One-click pipeline
python3 scripts/tpf-pipeline.py \
  --from-json examples/changsha-3day/input.json \
  --output-dir output \
  --with-metro --pretty

# Or step by step
python3 scripts/search_travel_info.py --city 长沙 --attractions 岳麓山 橘子洲 --pretty
python3 page-generator/scripts/tpf-generate.py --from-json input.json --pretty -o data/trip-data.json
python3 page-generator/scripts/tpf-cli.py validate
python3 page-generator/scripts/tpf-cli.py build
```

## Project Structure

```
china-travel-planner/
├── SKILL.md                          # Agent skill definition (start here)
├── scripts/
│   ├── tpf-pipeline.py               # One-click pipeline
│   ├── search_travel_info.py         # Tavily-powered travel guide search
│   ├── fetch_subway_data.py          # Metro line/station data (AMap)
│   ├── metro_hotel_match.py          # Hotel-to-metro matching
│   └── coverage_plan_notes.py        # Metro coverage planning
├── page-generator/
│   ├── scripts/
│   │   ├── tpf-cli.py               # validate / build / deploy
│   │   ├── tpf-generate.py          # JSON input → trip-data.json
│   │   └── wikimedia_image_search.py # Free image search
│   ├── schema/
│   │   ├── trip-schema.json          # JSON schema
│   │   └── trip-content-guidelines.md
│   └── templates/
│       ├── trip-page-tailwind.html   # HTML template
│       └── trip-renderer.js          # Client-side renderer
├── examples/
│   └── changsha-3day/                # End-to-end example
├── references/                       # Planning guides
└── docs/                             # GitHub Pages deployment
```

## Tools

| Script | Purpose |
|--------|---------|
| `tpf-pipeline.py` | Full pipeline: search → generate → validate → build |
| `search_travel_info.py` | Search travel guides via Tavily API |
| `tpf-generate.py` | Convert structured JSON to schema-compliant trip-data.json |
| `tpf-cli.py validate` | Validate trip-data.json against schema |
| `tpf-cli.py build` | Build static HTML page |
| `tpf-cli.py deploy` | Deploy to GitHub Pages via git worktree |
| `fetch_subway_data.py` | Fetch metro data from AMap |
| `wikimedia_image_search.py` | Search CC-licensed images from Wikimedia |

## Example

See [`examples/changsha-3day/`](examples/changsha-3day/) for a complete end-to-end example.

## License

MIT
