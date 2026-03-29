# travel-page-framework

The page generation engine for china-travel-planner. Converts structured trip data (JSON) into self-contained HTML itinerary pages.

## Structure

```
page-generator/
├── schema/
│   ├── trip-schema.json              # JSON schema for trip data
│   └── trip-content-guidelines.md    # Content writing guide
├── scripts/
│   ├── tpf-cli.py                    # validate / build / deploy
│   ├── tpf-generate.py               # Structured JSON → trip-data.json
│   └── wikimedia_image_search.py     # CC image search
└── templates/
    ├── trip-page-tailwind.html       # HTML template (Tailwind CSS)
    └── trip-renderer.js              # Client-side JS renderer
```

## How it works

1. AI agent produces structured input JSON (city, days, attractions, hotels, etc.)
2. `tpf-generate.py` converts it to a schema-compliant `trip-data.json`
3. `tpf-cli.py validate` checks against `trip-schema.json`
4. `tpf-cli.py build` inlines template + renderer + data into a single `dist/index.html`
5. `tpf-cli.py deploy` pushes to GitHub Pages via git worktree

## Key design decisions

- **Data-driven rendering**: All content lives in JSON, the template is purely presentational
- **Single-file output**: `build` produces a standalone HTML file with everything inlined
- **Schema contract**: `trip-schema.json` defines the interface between AI agent and page renderer
